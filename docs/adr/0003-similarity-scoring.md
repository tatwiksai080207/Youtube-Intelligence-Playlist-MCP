# ADR-0003: Similarity Scoring, Objective Weight Redistribution, and Diversity Ranking

- **Status:** Accepted
- **Date:** 2026-11-26
- **Decision Makers:** Molleti Tatwik Sai (owner), Madire Shiva Reddy, Mohammed Farhan
- **Task:** `TS-04`
- **GitHub Issue:** `#27` (task), `#28` (open Decision `G-01`)
- **GitHub PR:** `pending`
- **Requirements:** `FR-1.2`, `FR-1.3`, `FR-2.1`, `FR-2.2`, `NFR-1`, `NFR-5`, `SE-3`, `SB-3`
- **Brain Sources:**
  - [[brain/resources/tfidf-cosine-similarity|TF IDF and Cosine Similarity]]
  - [[brain/resources/channel-similarity|Channel Similarity Profiling and Ranking]]
  - [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]
  - [[brain/resources/nfr-targets|Non-Functional Requirements Targets and Error Mapping]]

## Context

`FR-1.2` (`get_similar_videos`) and `FR-2.2` (`get_similar_channels`) require deterministic, fast (`NFR-1` target `<= 150 ms` for up to `250` candidate videos), explainable ranking using solely objective YouTube metadata (`INV-01`, `FR-1.3`, `FR-2.2`). Popularity signals such as view counts, like counts, comment counts, and subscriber counts are strictly excluded at both schema validation (`src/yt_intel_mcp/schemas/`) and domain model boundaries (`VideoMeta` and `ChannelMeta` in `src/yt_intel_mcp/models.py`).

Candidate videos frequently arrive with sparse metadata: creator tags may be empty, descriptions can be short or absent, and live streams omit `duration_seconds`. Fixed additive scoring without active feature normalization unfairly penalizes valid matches or distorts cosine scores below calibrated thresholds.

## Decision

### 1. Frozen Default Feature Weights (`SimilarityConfig`)

Video similarity (`FR-1.2`) and channel similarity (`FR-2.2`) use the objective feature weights frozen in `src/yt_intel_mcp/config.py`:

| Domain | Feature | Default Weight | Signal Representation |
|---|---|---|---|
| Video (`FR-1.2`) | `title` | `0.35` | TF IDF cosine similarity over tokenized video titles |
| Video (`FR-1.2`) | `tags` | `0.25` | TF IDF cosine similarity over creator keyword tags |
| Video (`FR-1.2`) | `description` | `0.20` | TF IDF cosine similarity over sanitized prefix (`<= 500` chars) |
| Video (`FR-1.2`) | `category` | `0.10` | Exact equality (`1.0` if equal non empty `category_id`, else `0.0`) |
| Video (`FR-1.2`) | `duration` | `0.10` | Bounded relative closeness `1 - |a - b| / max(a, b, 1)` |
| Channel (`FR-2.2`) | `topic_categories` | `0.25` | Normalized topic overlap across Wikipedia topic identifiers |
| Channel (`FR-2.2`) | `keywords` | `0.20` | TF IDF cosine similarity over channel keywords and upload tags |
| Channel (`FR-2.2`) | Recent uploads profile | `0.55` | Aggregated TF IDF cosine similarity over up to `10` recent uploads |

Callers of `get_similar_videos` may override any subset of `{title, tags, description, category, duration}` via `scoring_weights`. Each supplied weight must lie in `[0.0, 1.0]`, unknown keys are rejected by JSON Schema `additionalProperties: false` (`NFR-5`), and domain validation raises `INVALID_ARGUMENT` pre quota if all active supplied weights sum to `0.0`.

### 2. Text Normalization, Sublinear TF IDF, and Sparse Cosine Scoring

- **Sanitization and tokenization (`INV-22`):** Strip URLs, control characters, and punctuation, lowercase ASCII and Unicode fold terms, remove English stopwords, keep tokens with length `>= 2`, and truncate `description` cleanly before scoring.
- **Sublinear term frequency:** For term $t$ in document $d$, $\text{tf}(t, d) = 1 + \ln(\text{count}(t, d))$ when $\text{count}(t, d) > 0$, otherwise $0$.
- **Smoothed inverse document frequency:** Across corpus size $N$ (seed plus candidate pool):
  $$\text{idf}(t) = \ln\left(\frac{1 + N}{1 + \text{df}(t)}\right) + 1$$
- **Cosine field score:** For field vectors $\mathbf{a}$ and $\mathbf{b}$, cosine score is $\frac{\mathbf{a} \cdot \mathbf{b}}{\|\mathbf{a}\|_2 \|\mathbf{b}\|_2} \in [0.0, 1.0]$.
- **Duration proximity:** When both videos provide positive integer `duration_seconds`, compute $1 - \frac{|d_{\text{seed}} - d_{\text{cand}}|}{\max(d_{\text{seed}}, d_{\text{cand}}, 1)} \in [0.0, 1.0]$.

### 3. Dynamic Missing Field Weight Redistribution

A feature $f$ is active for ranking a seed video against the candidate pool only when the seed carries usable signal for $f$ (non empty tokens for `title`/`tags`/`description`, non empty `category_id` for `category`, positive `duration_seconds` for `duration`). For example, if a seed video has zero creator tags or lacks duration (live broadcast), the unavailable feature is dropped from the active numerator and denominator and remaining active weights are renormalized:
$$w'_f = \frac{w_f}{\sum_{k \in \text{Active}} w_k}$$
If the seed carries a feature (such as `tags`) and a candidate leaves it empty, that candidate receives $0.0$ for $f$ so richer matching candidates rank higher. For `channel` comparison, missing `topic_categories` or missing `keywords` follow the identical seed activity normalization rule across `{topics, keywords, recent_uploads}` (`SimilarityConfig.topics_weight`, `SimilarityConfig.keywords_weight`, and residual upload content weight `0.55`).

### 4. Diversity Aware Ranking and Deterministic Tie Breaking (`FR-1.2`)

1. Score candidates with weighted sum $\sum_{f \in \text{Active}} w'_f \cdot s_f(\text{seed}, c)$ in `[0.0, 1.0]`.
2. Exclude the seed video ID (or seed channel ID) and unavailable videos.
3. Re rank top candidates deterministically using Maximal Marginal Relevance with $\lambda = 0.85$ against already selected items (`0.85 * base_score - 0.15 * max_pairwise_cosine`) and cap identical creator repetitions when sufficient diverse creators exist.
4. Break score ties deterministically by ascending lexicographic `video_id` (or `channel_id`), ensuring reproducible results across fixture and CI runs.
5. Attach top shared human readable keywords (`matched_signals`, capped and sanitized) so callers see why each recommendation matched without exposing raw prompt injection payloads (`INV-22`).

### 5. Explicit Exclusions and Open Decision Reference

- **Clickbait penalty not adopted (`G-07`):** Clickbait heuristics or like ratios are excluded because they do not appear in `SRS Section 4.1.2` and violate objective metadata invariance (`INV-01`).
- **Nonexistent seed channel error (`G-01`):** Whether `get_similar_channels` maps a missing or nonexistent channel to `INVALID_ARGUMENT` (existing `ErrorCode`) or introduces `CHANNEL_UNAVAILABLE` is tracked in open team decision `#28` prior to `TS-11`.

## Alternatives Considered

- **Heavy external vector or transformer dependencies:** Rejected because deterministic pure Python sparse TF IDF dictionaries run in single digit milliseconds for `250` candidates (`<< 150 ms` `NFR-1`), require zero GPU/model weights, and match `ADR-0001` lightweight dependency policy.
- **Popularity tie breaking (`viewCount` or `subscriberCount`):** Rejected as a direct violation of `FR-1.3`, `FR-2.2`, and `INV-01`.

## Consequences

### Positive
- Pure functions in future `TS-08` (`yt_intel_mcp.analysis.similarity`) operate cleanly on `VideoMeta` and `ChannelMeta` with zero network I/O or `YouTubeProvider` coupling.
- Redistribution prevents artificial score ceilings when creators omit optional fields such as tags or descriptions.
- Performance target `NFR-1` (`<= 150 ms` for `250` items) is easily met using sparse dictionary dot products.

### Trade Offs
- Dynamic redistribution assumes all text token weights supplied for remaining active fields still carry at least one positive weight (enforced pre quota by `sum(active_weights) > 0`, otherwise `INVALID_ARGUMENT`).
