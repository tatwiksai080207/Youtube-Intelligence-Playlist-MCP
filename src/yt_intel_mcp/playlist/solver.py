"""Relevance-maximising constrained playlist selection solver (MF-10, FR-5.2, NFR-1)."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from yt_intel_mcp.config import SimilarityConfig
from yt_intel_mcp.durations import format_duration, is_live_or_zero_duration
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.playlist.constraints import (
    MAX_PLAYLIST_VIDEOS,
    MAX_TOLERANCE_PERCENT,
    PlaylistConstraints,
)
from yt_intel_mcp.playlist.language import (
    AudioLanguageStatus,
    LanguageCheckResult,
    evaluate_video_audio_language,
)
from yt_intel_mcp.similarity.text import (
    DEFAULT_DESCRIPTION_PREFIX_LENGTH,
    score_texts_cosine,
    tokenize_tags,
    tokenize_text,
)

__all__ = [
    "BindingConstraint",
    "PlaylistSolution",
    "SelectedPlaylistVideo",
    "SolverAlgorithm",
    "score_candidates_for_topic",
    "solve_playlist_selection",
]

BindingConstraint = Literal[
    "language_filter",
    "max_video_minutes",
    "max_videos_capacity",
    "target_total_window_floor",
    "insufficient_candidate_pool",
]

SolverAlgorithm = Literal[
    "exact",
    "bucketed_dp_local_search",
    "bitset_local_search",
]

_SCORE_SCALE = 1_000_000_000
_MAX_EXACT_DP_WORK = 250_000
_MAX_EXACT_BNB_WORK = 1_500_000
_MAX_EXACT_BNB_N = 35
_MAX_BUCKETS = 240
_SCALED_BUCKETS = 36


@dataclass(frozen=True, slots=True)
class SelectedPlaylistVideo:
    """One selected candidate video with objective relevance and audio-language status."""

    video: VideoMeta
    relevance_score: float
    duration_seconds: int
    audio_language_status: AudioLanguageStatus
    audio_language_label: str
    is_audio_language_unverified: bool


@dataclass(frozen=True, slots=True)
class PlaylistSolution:
    """Deterministic constrained playlist solution maximizing topic relevance (FR-5.2, NFR-1)."""

    selected_videos: tuple[SelectedPlaylistVideo, ...]
    total_duration_seconds: int
    total_duration_human: str
    total_relevance_score: float
    target_min_seconds: int
    target_max_seconds: int
    candidates_retrieved: int
    candidates_eligible: int
    algorithm_used: SolverAlgorithm


@dataclass(frozen=True, slots=True)
class _Candidate:
    """Internal pre-scored eligible candidate ordered by (-scaled_score, video_id)."""

    video: VideoMeta
    duration: int
    scaled_score: int
    relevance_score: float
    language_check: LanguageCheckResult
    id_bit: int = 0


def score_candidates_for_topic(
    topic: str,
    videos: Sequence[VideoMeta],
    *,
    similarity_config: SimilarityConfig | None = None,
) -> dict[str, float]:
    """Compute objective TF-IDF cosine relevance in [0.0, 1.0] per video_id (FR-5.2, INV-01)."""
    if not videos:
        return {}

    cfg = similarity_config or SimilarityConfig()
    text_weight_sum = cfg.title_weight + cfg.tags_weight + cfg.description_weight
    if text_weight_sum <= 0.0:
        raise ValueError("Text similarity weights must have a positive sum.")

    w_title = cfg.title_weight / text_weight_sum
    w_tags = cfg.tags_weight / text_weight_sum
    w_desc = cfg.description_weight / text_weight_sum

    unique_videos = _deduplicate_videos(videos)
    topic_tokens = tokenize_text(topic)
    if not topic_tokens:
        return {video.video_id: 0.0 for video in unique_videos}

    title_docs = [tokenize_text(video.title) for video in unique_videos]
    tag_docs = [tokenize_tags(video.tags) for video in unique_videos]
    desc_docs = [
        tokenize_text(video.description, max_length=DEFAULT_DESCRIPTION_PREFIX_LENGTH)
        for video in unique_videos
    ]

    title_scores = (
        score_texts_cosine(topic_tokens, title_docs)
        if any(title_docs)
        else [0.0] * len(unique_videos)
    )
    tag_scores = (
        score_texts_cosine(topic_tokens, tag_docs) if any(tag_docs) else [0.0] * len(unique_videos)
    )
    desc_scores = (
        score_texts_cosine(topic_tokens, desc_docs)
        if any(desc_docs)
        else [0.0] * len(unique_videos)
    )

    scores: dict[str, float] = {}
    for video, s_t, s_g, s_d in zip(
        unique_videos, title_scores, tag_scores, desc_scores, strict=True
    ):
        blended = w_title * s_t + w_tags * s_g + w_desc * s_d
        clamped = min(1.0, max(0.0, blended))
        scores[video.video_id] = round(clamped, 9)
    return scores


def _deduplicate_videos(videos: Sequence[VideoMeta]) -> list[VideoMeta]:
    seen: set[str] = set()
    unique: list[VideoMeta] = []
    for video in videos:
        if video.video_id in seen:
            continue
        seen.add(video.video_id)
        unique.append(video)
    return unique


def _quantize_score(raw_score: float, video_id: str) -> tuple[int, float]:
    if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
        raise ValueError(f"Relevance score for {video_id!r} must be numeric.")
    value = float(raw_score)
    if math.isnan(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"Relevance score for {video_id!r} must lie within [0.0, 1.0].")
    rounded = round(value, 9)
    return round(rounded * _SCORE_SCALE), rounded


def _is_playable_non_live(video: VideoMeta) -> bool:
    if not video.is_available:
        return False
    if video.privacy_status.strip().lower() == "private":
        return False
    if is_live_or_zero_duration(
        video.duration_seconds, live_broadcast_content=video.live_broadcast_content
    ):
        return False
    return video.duration_seconds is not None and video.duration_seconds >= 1


def _decode_mask_indices(mask: int) -> list[int]:
    indices: list[int] = []
    remaining = mask
    while remaining:
        lsb = remaining & -remaining
        indices.append(lsb.bit_length() - 1)
        remaining ^= lsb
    return indices


def _is_lex_smaller_id_mask(id_mask_a: int, id_mask_b: int) -> bool:
    """Return True iff sorted video_id tuple for id_mask_a < sorted tuple for id_mask_b."""
    diff = id_mask_a ^ id_mask_b
    if diff == 0:
        return False
    lsb = diff & -diff
    if id_mask_a & lsb:
        # id_mask_b lacks lsb: b is smaller only if b has no elements larger than lsb.
        return id_mask_b > lsb
    # id_mask_a lacks lsb: a is smaller iff a ended before lsb.
    return id_mask_a < lsb


def _is_better_state(
    score_a: int,
    id_mask_a: int,
    score_b: int,
    id_mask_b: int,
) -> bool:
    if score_a != score_b:
        return score_a > score_b
    return _is_lex_smaller_id_mask(id_mask_a, id_mask_b)


def _solve_small_exact_dp(
    items: Sequence[_Candidate],
    target_min: int,
    target_max: int,
    max_k: int,
) -> int | None:
    """Solve to global exact optimality via sparse cardinality DP when state space is small."""
    # layers[k] maps exact_dur -> (scaled_score, mask, id_mask)
    layers: list[dict[int, tuple[int, int, int]]] = [{} for _ in range(max_k + 1)]
    layers[0][0] = (0, 0, 0)

    for idx, item in enumerate(items):
        dur = item.duration
        if dur > target_max:
            continue
        score = item.scaled_score
        bit = 1 << idx
        id_bit = item.id_bit
        upper_k = min(max_k, idx + 1)
        for k in range(upper_k, 0, -1):
            prev_map = layers[k - 1]
            if not prev_map:
                continue
            cur_map = layers[k]
            for prev_dur, (prev_score, prev_mask, prev_id_mask) in prev_map.items():
                new_dur = prev_dur + dur
                if new_dur > target_max:
                    continue
                new_score = prev_score + score
                new_id_mask = prev_id_mask | id_bit
                existing = cur_map.get(new_dur)
                if existing is None or _is_better_state(
                    new_score, new_id_mask, existing[0], existing[2]
                ):
                    cur_map[new_dur] = (new_score, prev_mask | bit, new_id_mask)

    best_score = -1
    best_mask = 0
    best_id_mask = 0
    for k in range(1, max_k + 1):
        for dur, (score, mask, id_mask) in layers[k].items():
            if target_min <= dur <= target_max and (
                best_mask == 0 or _is_better_state(score, id_mask, best_score, best_id_mask)
            ):
                best_score = score
                best_mask = mask
                best_id_mask = id_mask
    return best_mask if best_mask != 0 else None


def _compute_suffix_reachability_masks(
    items: Sequence[_Candidate],
    target_max: int,
    max_k: int,
) -> list[list[int]]:
    """Build suffix OR bitmasks suf[idx][r] = reachable durations using <= r items from idx..N-1."""
    n = len(items)
    cap_mask = (1 << (target_max + 1)) - 1
    exact: list[list[int]] = [[0] * (max_k + 1) for _ in range(n + 1)]
    exact[n][0] = 1
    for idx in range(n - 1, -1, -1):
        dur = items[idx].duration
        exact[idx][0] = 1
        for k in range(1, max_k + 1):
            without_cur = exact[idx + 1][k]
            with_cur = ((exact[idx + 1][k - 1] << dur) & cap_mask) if dur <= target_max else 0
            exact[idx][k] = without_cur | with_cur

    cumulative: list[list[int]] = []
    for idx in range(n + 1):
        row = [0] * (max_k + 1)
        running = exact[idx][0]
        row[0] = running
        for k in range(1, max_k + 1):
            running |= exact[idx][k]
            row[k] = running
        cumulative.append(row)
    return cumulative


def _solve_exact_branch_and_bound(
    items: Sequence[_Candidate],
    target_min: int,
    target_max: int,
    max_k: int,
    incumbent_mask: int | None,
    budget_ms: float,
) -> int | None:
    """Cardinality bounded branch-and-bound with bitset reachability and sound upper bounds."""
    n = len(items)
    suf_or = _compute_suffix_reachability_masks(items, target_max, max_k)
    full_window_mask = ((1 << (target_max + 1)) - 1) ^ ((1 << target_min) - 1)
    if (suf_or[0][max_k] & full_window_mask) == 0:
        return None

    prefix_scores = [0] * (n + 1)
    for idx, item in enumerate(items):
        prefix_scores[idx + 1] = prefix_scores[idx] + item.scaled_score

    density_order = sorted(
        range(n),
        key=lambda i: (-(items[i].scaled_score / items[i].duration), items[i].video.video_id),
    )

    def _upper_bound(start_idx: int, rem_k: int, rem_dur: int) -> int:
        avail = n - start_idx
        if rem_k <= 0 or avail <= 0 or rem_dur <= 0:
            return 0
        count_cap = min(rem_k, avail)
        top_k_bound = prefix_scores[start_idx + count_cap] - prefix_scores[start_idx]

        frac_bound = 0
        rem_cap = rem_dur
        for d_idx in density_order:
            if d_idx < start_idx:
                continue
            item = items[d_idx]
            if item.duration <= rem_cap:
                frac_bound += item.scaled_score
                rem_cap -= item.duration
                if rem_cap == 0:
                    break
            else:
                frac_bound += math.ceil(item.scaled_score * rem_cap / item.duration)
                break
        return min(top_k_bound, frac_bound)

    best_score = -1
    best_mask = 0
    best_id_mask = 0
    if incumbent_mask is not None and incumbent_mask != 0:
        inc_indices = _decode_mask_indices(incumbent_mask)
        best_score = sum(items[i].scaled_score for i in inc_indices)
        best_mask = incumbent_mask
        for i in inc_indices:
            best_id_mask |= items[i].id_bit

    seen: dict[tuple[int, int, int], tuple[int, int]] = {}
    deadline = time.perf_counter() + max(0.01, budget_ms / 1000.0)
    nodes = 0
    timed_out = False

    def _dfs(
        idx: int, count: int, cur_dur: int, cur_score: int, cur_mask: int, cur_id_mask: int
    ) -> None:
        nonlocal best_score, best_mask, best_id_mask, nodes, timed_out
        if timed_out:
            return
        nodes += 1
        if (nodes & 1023) == 0 and time.perf_counter() >= deadline:
            timed_out = True
            return

        if (
            count > 0
            and target_min <= cur_dur <= target_max
            and cur_mask != best_mask
            and (
                best_mask == 0 or _is_better_state(cur_score, cur_id_mask, best_score, best_id_mask)
            )
        ):
            best_score = cur_score
            best_mask = cur_mask
            best_id_mask = cur_id_mask

        if idx >= n or count >= max_k:
            return

        rem_k = max_k - count
        rem_dur = target_max - cur_dur
        if max(0, target_min - cur_dur) > rem_dur:
            return

        if ((suf_or[idx][rem_k] << cur_dur) & full_window_mask) == 0:
            return

        if best_mask != 0:
            ub = cur_score + _upper_bound(idx, rem_k, rem_dur)
            if ub < best_score:
                return

        state_key = (idx, count, cur_dur)
        prev_best = seen.get(state_key)
        if prev_best is not None:
            prev_score, prev_id_mask = prev_best
            if cur_score < prev_score:
                return
            if cur_score == prev_score and not _is_lex_smaller_id_mask(cur_id_mask, prev_id_mask):
                return
        seen[state_key] = (cur_score, cur_id_mask)

        item = items[idx]
        if item.duration <= rem_dur:
            _dfs(
                idx + 1,
                count + 1,
                cur_dur + item.duration,
                cur_score + item.scaled_score,
                cur_mask | (1 << idx),
                cur_id_mask | item.id_bit,
            )
        _dfs(idx + 1, count, cur_dur, cur_score, cur_mask, cur_id_mask)

    _dfs(0, 0, 0, 0, 0, 0)
    return best_mask if best_mask != 0 else None


def _local_search_refine(
    items: Sequence[_Candidate],
    start_mask: int,
    target_min: int,
    target_max: int,
    max_k: int,
    deadline: float,
) -> int:
    """Refine a feasible exact subset via add, drop, and 1-for-1 swap moves in exact seconds."""
    n = len(items)
    chosen = _decode_mask_indices(start_mask)
    cur_dur = sum(items[i].duration for i in chosen)
    if not (1 <= len(chosen) <= max_k and target_min <= cur_dur <= target_max):
        return start_mask

    cur_mask = start_mask
    cur_score = sum(items[i].scaled_score for i in chosen)
    cur_id_mask = 0
    for i in chosen:
        cur_id_mask |= items[i].id_bit

    steps = 0
    while steps < 32 and time.perf_counter() < deadline:
        steps += 1
        improved = False
        best_next_mask = cur_mask
        best_next_score = cur_score
        best_next_id_mask = cur_id_mask
        best_next_dur = cur_dur

        chosen_indices = _decode_mask_indices(cur_mask)
        count = len(chosen_indices)

        # Add move (items sorted descending by scaled_score => break once below best_next_score)
        if count < max_k:
            rem_cap = target_max - cur_dur
            for j in range(n):
                item_j = items[j]
                cand_score = cur_score + item_j.scaled_score
                if cand_score < best_next_score:
                    break
                bit_j = 1 << j
                if cur_mask & bit_j or item_j.duration > rem_cap:
                    continue
                cand_id_mask = cur_id_mask | item_j.id_bit
                if cand_score > best_next_score or _is_lex_smaller_id_mask(
                    cand_id_mask, best_next_id_mask
                ):
                    best_next_score = cand_score
                    best_next_mask = cur_mask | bit_j
                    best_next_id_mask = cand_id_mask
                    best_next_dur = cur_dur + item_j.duration
                    improved = True

        # Drop move (removes zero-score items when remaining duration still satisfies target_min)
        if count > 1:
            for i in chosen_indices:
                item_i = items[i]
                cand_dur = cur_dur - item_i.duration
                if cand_dur < target_min:
                    continue
                cand_score = cur_score - item_i.scaled_score
                if cand_score < best_next_score:
                    continue
                cand_id_mask = cur_id_mask & ~item_i.id_bit
                if cand_score > best_next_score or _is_lex_smaller_id_mask(
                    cand_id_mask, best_next_id_mask
                ):
                    best_next_score = cand_score
                    best_next_mask = cur_mask & ~(1 << i)
                    best_next_id_mask = cand_id_mask
                    best_next_dur = cand_dur
                    improved = True

        # 1-for-1 swap move (early exit when item_j score can no longer match best_next_score)
        for i in chosen_indices:
            item_i = items[i]
            base_score = cur_score - item_i.scaled_score
            base_dur = cur_dur - item_i.duration
            without_i = cur_mask & ~(1 << i)
            without_i_id = cur_id_mask & ~item_i.id_bit
            for j in range(n):
                item_j = items[j]
                cand_score = base_score + item_j.scaled_score
                if cand_score < best_next_score:
                    break
                bit_j = 1 << j
                if cur_mask & bit_j:
                    continue
                cand_dur = base_dur + item_j.duration
                if not (target_min <= cand_dur <= target_max):
                    continue
                cand_id_mask = without_i_id | item_j.id_bit
                if cand_score > best_next_score or _is_lex_smaller_id_mask(
                    cand_id_mask, best_next_id_mask
                ):
                    best_next_score = cand_score
                    best_next_mask = without_i | bit_j
                    best_next_id_mask = cand_id_mask
                    best_next_dur = cand_dur
                    improved = True

        if not improved:
            break
        cur_mask = best_next_mask
        cur_score = best_next_score
        cur_id_mask = best_next_id_mask
        cur_dur = best_next_dur

    return cur_mask


def _solve_bucketed_dp(
    items: Sequence[_Candidate],
    target_min: int,
    target_max: int,
    max_k: int,
) -> int | None:
    """Fast flat-array bucketed cardinality DP preserving exact seconds and O(1) tie breaking."""
    bucket_count = _SCALED_BUCKETS if (len(items) > 60 and max_k > 10) else _MAX_BUCKETS
    step = max(1, (target_max + bucket_count - 1) // bucket_count)
    slots_len = (target_max // step) + 1

    best_s = [[-1] * slots_len for _ in range(max_k + 1)]
    best_d = [[0] * slots_len for _ in range(max_k + 1)]
    best_m = [[0] * slots_len for _ in range(max_k + 1)]
    best_idm = [[0] * slots_len for _ in range(max_k + 1)]
    active: list[list[int]] = [[] for _ in range(max_k + 1)]

    best_s[0][0] = 0
    active[0].append(0)

    for idx, item in enumerate(items):
        dur = item.duration
        if dur > target_max:
            continue
        score = item.scaled_score
        bit = 1 << idx
        id_bit = item.id_bit
        upper_k = min(max_k, idx + 1)
        max_prev_dur = target_max - dur
        for k in range(upper_k, 0, -1):
            prev_active = active[k - 1]
            if not prev_active:
                continue
            ps = best_s[k - 1]
            pd = best_d[k - 1]
            pm = best_m[k - 1]
            pidm = best_idm[k - 1]
            cs = best_s[k]
            cd = best_d[k]
            cm = best_m[k]
            cidm = best_idm[k]
            cur_active = active[k]
            for pb in prev_active:
                prev_dur = pd[pb]
                if prev_dur > max_prev_dur:
                    continue
                new_dur = prev_dur + dur
                new_b = new_dur // step
                new_score = ps[pb] + score
                old_score = cs[new_b]
                if old_score < 0:
                    cs[new_b] = new_score
                    cd[new_b] = new_dur
                    cm[new_b] = pm[pb] | bit
                    cidm[new_b] = pidm[pb] | id_bit
                    cur_active.append(new_b)
                elif new_score > old_score:
                    cs[new_b] = new_score
                    cd[new_b] = new_dur
                    cm[new_b] = pm[pb] | bit
                    cidm[new_b] = pidm[pb] | id_bit
                elif new_score == old_score:
                    new_idm = pidm[pb] | id_bit
                    if _is_lex_smaller_id_mask(new_idm, cidm[new_b]):
                        cd[new_b] = new_dur
                        cm[new_b] = pm[pb] | bit
                        cidm[new_b] = new_idm

    winner_score = -1
    winner_mask = 0
    winner_id_mask = 0
    for k in range(1, max_k + 1):
        cs = best_s[k]
        cd = best_d[k]
        cm = best_m[k]
        cidm = best_idm[k]
        for b in active[k]:
            dur = cd[b]
            if target_min <= dur <= target_max:
                score = cs[b]
                idm = cidm[b]
                if winner_mask == 0 or _is_better_state(score, idm, winner_score, winner_id_mask):
                    winner_score = score
                    winner_mask = cm[b]
                    winner_id_mask = idm

    return winner_mask if winner_mask != 0 else None


def _solve_exact_bitset_fallback(
    items: Sequence[_Candidate],
    target_min: int,
    target_max: int,
    max_k: int,
) -> int | None:
    """Exact cardinality bitset feasibility check and high-relevance backtracking."""
    n = len(items)
    cap_mask = (1 << (target_max + 1)) - 1
    window_mask = cap_mask ^ ((1 << target_min) - 1)

    layers: list[list[int]] = [[0] * (max_k + 1)]
    layers[0][0] = 1
    for idx, item in enumerate(items):
        prev = layers[idx]
        nxt = prev.copy()
        dur = item.duration
        if dur <= target_max:
            upper_k = min(max_k, idx + 1)
            for k in range(1, upper_k + 1):
                nxt[k] |= (prev[k - 1] << dur) & cap_mask
        layers.append(nxt)

    final_layer = layers[n]
    feasible_c = 0
    feasible_mask = 0
    for c in range(1, max_k + 1):
        hit = final_layer[c] & window_mask
        if hit:
            feasible_c = c
            feasible_mask = hit
            break

    if feasible_c == 0:
        return None

    target_dur = feasible_mask.bit_length() - 1
    rem_c = feasible_c
    rem_dur = target_dur
    chosen_mask = 0

    for idx in range(n - 1, -1, -1):
        if rem_c == 0:
            break
        prev_layer = layers[idx]
        if (prev_layer[rem_c] >> rem_dur) & 1:
            continue
        dur = items[idx].duration
        if dur <= rem_dur and ((prev_layer[rem_c - 1] >> (rem_dur - dur)) & 1):
            chosen_mask |= 1 << idx
            rem_c -= 1
            rem_dur -= dur

    return chosen_mask if chosen_mask != 0 else None


def _closest_achievable_under_ceiling(
    items: Sequence[_Candidate],
    target_max: int,
    max_k: int,
) -> int | None:
    """Compute highest achievable duration <= target_max among <= max_k items."""
    if not items or max_k <= 0:
        return None
    cap_mask = (1 << (target_max + 1)) - 1
    dp = [0] * (max_k + 1)
    dp[0] = 1
    for item in items:
        dur = item.duration
        if dur > target_max:
            continue
        for k in range(max_k, 0, -1):
            dp[k] |= (dp[k - 1] << dur) & cap_mask

    combined = 0
    for k in range(1, max_k + 1):
        combined |= dp[k]
    if combined == 0:
        return None
    return combined.bit_length() - 1


def _diagnose_unsatisfiable(
    *,
    candidates_retrieved: int,
    playable_videos: Sequence[VideoMeta],
    lang_results: Sequence[tuple[VideoMeta, LanguageCheckResult]],
    eligible_items: Sequence[_Candidate],
    constraints: PlaylistConstraints,
    unavailable_or_live_count: int,
    language_mismatch_count: int,
    language_missing_count: int,
    over_max_video_count: int,
) -> ToolError:
    """Build rich FR-5.2 / INV-11 CONSTRAINTS_UNSATISFIABLE error with binding cause & options."""
    target_min = constraints.target_min_seconds
    target_max = constraints.target_max_seconds
    eff_max_k = min(constraints.max_videos, len(eligible_items)) if eligible_items else 0
    closest_seconds = (
        _closest_achievable_under_ceiling(eligible_items, target_max, eff_max_k)
        if eligible_items
        else None
    )

    sum_all_eligible = sum(item.duration for item in eligible_items)
    durations_desc = sorted((item.duration for item in eligible_items), reverse=True)
    max_with_k_cap = sum(durations_desc[: constraints.max_videos])

    lang_passed_durations = [
        video.duration_seconds
        for video, res in lang_results
        if res.eligible and video.duration_seconds is not None
    ]
    missing_lang_fit_durations = [
        video.duration_seconds
        for video, res in lang_results
        if (
            res.status == "missing_excluded"
            and video.duration_seconds is not None
            and video.duration_seconds <= constraints.effective_max_video_seconds
        )
    ]

    binding_constraint: BindingConstraint
    if candidates_retrieved == 0 or not playable_videos:
        binding_constraint = "insufficient_candidate_pool"
    elif not any(res.eligible for _, res in lang_results):
        binding_constraint = "language_filter"
    elif not eligible_items:
        if constraints.max_video_minutes is not None and over_max_video_count > 0:
            binding_constraint = "max_video_minutes"
        else:
            binding_constraint = "insufficient_candidate_pool"
    elif max_with_k_cap < target_min:
        if len(eligible_items) > constraints.max_videos and sum_all_eligible >= target_min:
            binding_constraint = "max_videos_capacity"
        elif (
            not constraints.allow_unknown_language
            and language_missing_count > 0
            and sum_all_eligible + sum(missing_lang_fit_durations) >= target_min
        ):
            binding_constraint = "language_filter"
        elif constraints.max_video_minutes is not None and over_max_video_count > 0:
            binding_constraint = "max_video_minutes"
        else:
            binding_constraint = "insufficient_candidate_pool"
    else:
        binding_constraint = "target_total_window_floor"

    options: list[dict[str, Any]] = [
        {
            "action": "broader_search",
            "description": (
                "Run a broader YouTube search to retrieve additional candidate videos."
            ),
            "estimated_extra_quota": {"search_calls": 1, "units": 1},
            "requires_confirmation": True,
        }
    ]

    if language_missing_count > 0 and not constraints.allow_unknown_language:
        options.append(
            {
                "action": "relax_constraint",
                "parameter": "allow_unknown_language",
                "suggested_value": True,
                "description": (
                    f"Allow {language_missing_count} candidate video(s) missing "
                    "defaultAudioLanguage (labelled 'Audio language unverified')."
                ),
                "requires_confirmation": True,
            }
        )

    if constraints.language is not None and language_mismatch_count > 0:
        options.append(
            {
                "action": "relax_constraint",
                "parameter": "language",
                "suggested_value": None,
                "description": (
                    f"Remove the '{constraints.language}' spoken audio-language filter "
                    f"({language_mismatch_count} video(s) had a different language)."
                ),
                "requires_confirmation": True,
            }
        )

    if over_max_video_count > 0 and constraints.max_video_minutes is not None:
        over_durations = sorted(
            d for d in lang_passed_durations if d > constraints.effective_max_video_seconds
        )
        if over_durations:
            min_needed_minutes = min(
                constraints.target_total_minutes,
                round(math.ceil(over_durations[0] / 60.0), 2),
            )
            if min_needed_minutes > constraints.max_video_minutes:
                options.append(
                    {
                        "action": "relax_constraint",
                        "parameter": "max_video_minutes",
                        "suggested_value": min_needed_minutes,
                        "description": (
                            f"Increase max_video_minutes from {constraints.max_video_minutes:g} "
                            f"to {min_needed_minutes:g} minutes to admit "
                            f"{over_max_video_count} longer candidate(s)."
                        ),
                        "requires_confirmation": True,
                    }
                )

    if (
        len(eligible_items) > constraints.max_videos
        and sum_all_eligible >= target_min
        and constraints.max_videos < MAX_PLAYLIST_VIDEOS
    ):
        acc = 0
        needed_k = 0
        for dur in durations_desc[:MAX_PLAYLIST_VIDEOS]:
            acc += dur
            needed_k += 1
            if acc >= target_min:
                break
        if acc >= target_min and needed_k > constraints.max_videos:
            options.append(
                {
                    "action": "relax_constraint",
                    "parameter": "max_videos",
                    "suggested_value": needed_k,
                    "description": (
                        f"Raise max_videos from {constraints.max_videos} to {needed_k}."
                    ),
                    "requires_confirmation": True,
                }
            )

    if closest_seconds is not None and closest_seconds < target_min:
        raw_tol = ((target_max - closest_seconds) / target_max) * 100.0
        needed_tol = min(MAX_TOLERANCE_PERCENT, math.ceil(raw_tol * 100.0) / 100.0)
        if raw_tol <= MAX_TOLERANCE_PERCENT and needed_tol > constraints.tolerance_percent:
            options.append(
                {
                    "action": "relax_constraint",
                    "parameter": "tolerance_percent",
                    "suggested_value": needed_tol,
                    "description": (
                        f"Widen tolerance_percent from {constraints.tolerance_percent:g}% to "
                        f"{needed_tol:g}% to accept the closest total duration "
                        f"({format_duration(closest_seconds)})."
                    ),
                    "requires_confirmation": True,
                }
            )

    details: dict[str, Any] = {
        "candidates_retrieved": candidates_retrieved,
        "candidates_eligible": len(eligible_items),
        "binding_constraint": binding_constraint,
        "requires_user_choice": True,
        "target_window_seconds": {"min": target_min, "max": target_max},
        "closest_achievable_seconds": closest_seconds,
        "rejection_summary": {
            "unavailable_or_live": unavailable_or_live_count,
            "language_mismatch": language_mismatch_count,
            "language_missing": language_missing_count,
            "exceeds_max_video_minutes": over_max_video_count,
        },
        "options": options,
    }

    message = (
        f"No compliant playlist combination was found among the {candidates_retrieved} "
        f"candidates retrieved (this does not mean none exists on YouTube). "
        f"Binding constraint: {binding_constraint}. "
        f"Target window is {format_duration(target_min)} to {format_duration(target_max)}. "
        "Please choose either a broader search (estimated extra cost: 1 search call + "
        "1 metadata unit) or one of the named constraint relaxations in details.options."
    )
    return ToolError(ErrorCode.CONSTRAINTS_UNSATISFIABLE, message, details=details)


def solve_playlist_selection(
    videos: Sequence[VideoMeta],
    constraints: PlaylistConstraints,
    *,
    relevance_scores: Mapping[str, float] | None = None,
    similarity_config: SimilarityConfig | None = None,
    search_budget_ms: float = 200.0,
) -> PlaylistSolution:
    """Select an optimal relevance-maximising subset strictly satisfying FR-5.1..5.2."""
    unique_videos = _deduplicate_videos(videos)
    candidates_retrieved = len(unique_videos)

    playable_videos: list[VideoMeta] = []
    unavailable_or_live_count = 0
    for video in unique_videos:
        if _is_playable_non_live(video):
            playable_videos.append(video)
        else:
            unavailable_or_live_count += 1

    lang_results: list[tuple[VideoMeta, LanguageCheckResult]] = []
    language_mismatch_count = 0
    language_missing_count = 0
    over_max_video_count = 0
    duration_and_lang_videos: list[tuple[VideoMeta, LanguageCheckResult]] = []

    max_video_cap = constraints.effective_max_video_seconds
    for video in playable_videos:
        lang_res = evaluate_video_audio_language(
            video,
            constraints.language,
            allow_unknown_language=constraints.allow_unknown_language,
        )
        lang_results.append((video, lang_res))
        if not lang_res.eligible:
            if lang_res.status == "mismatch":
                language_mismatch_count += 1
            else:
                language_missing_count += 1
            continue

        assert video.duration_seconds is not None
        if video.duration_seconds > max_video_cap:
            over_max_video_count += 1
            continue
        duration_and_lang_videos.append((video, lang_res))

    if not duration_and_lang_videos:
        raise _diagnose_unsatisfiable(
            candidates_retrieved=candidates_retrieved,
            playable_videos=playable_videos,
            lang_results=lang_results,
            eligible_items=[],
            constraints=constraints,
            unavailable_or_live_count=unavailable_or_live_count,
            language_mismatch_count=language_mismatch_count,
            language_missing_count=language_missing_count,
            over_max_video_count=over_max_video_count,
        )

    score_map: Mapping[str, float]
    if relevance_scores is None:
        score_map = score_candidates_for_topic(
            constraints.topic,
            [video for video, _ in duration_and_lang_videos],
            similarity_config=similarity_config,
        )
    else:
        score_map = relevance_scores

    raw_items: list[_Candidate] = []
    for video, lang_res in duration_and_lang_videos:
        assert video.duration_seconds is not None
        scaled_score, clamped_score = _quantize_score(
            score_map.get(video.video_id, 0.0), video.video_id
        )
        raw_items.append(
            _Candidate(
                video=video,
                duration=video.duration_seconds,
                scaled_score=scaled_score,
                relevance_score=clamped_score,
                language_check=lang_res,
            )
        )

    # Assign id_bit by sorted video_id order, then sort by (-scaled_score, video_id)
    id_order = sorted(raw_items, key=lambda c: c.video.video_id)
    id_bit_by_vid = {item.video.video_id: (1 << rank) for rank, item in enumerate(id_order)}
    eligible_items = [
        _Candidate(
            video=item.video,
            duration=item.duration,
            scaled_score=item.scaled_score,
            relevance_score=item.relevance_score,
            language_check=item.language_check,
            id_bit=id_bit_by_vid[item.video.video_id],
        )
        for item in sorted(raw_items, key=lambda c: (-c.scaled_score, c.video.video_id))
    ]

    target_min = constraints.target_min_seconds
    target_max = constraints.target_max_seconds
    n_elig = len(eligible_items)
    max_k = min(constraints.max_videos, n_elig)

    longest_sum = sum(sorted((c.duration for c in eligible_items), reverse=True)[:max_k])
    if longest_sum < target_min:
        raise _diagnose_unsatisfiable(
            candidates_retrieved=candidates_retrieved,
            playable_videos=playable_videos,
            lang_results=lang_results,
            eligible_items=eligible_items,
            constraints=constraints,
            unavailable_or_live_count=unavailable_or_live_count,
            language_mismatch_count=language_mismatch_count,
            language_missing_count=language_missing_count,
            over_max_video_count=over_max_video_count,
        )

    algorithm_used: SolverAlgorithm = "bucketed_dp_local_search"
    best_mask: int | None = None
    exact_work = n_elig * max_k * (target_max + 1)
    is_exact_regime = exact_work <= _MAX_EXACT_BNB_WORK or n_elig <= _MAX_EXACT_BNB_N

    if exact_work <= _MAX_EXACT_DP_WORK and target_max <= 3_600:
        best_mask = _solve_small_exact_dp(eligible_items, target_min, target_max, max_k)
        algorithm_used = "exact"
    else:
        bucket_mask = _solve_bucketed_dp(eligible_items, target_min, target_max, max_k)
        if bucket_mask is not None:
            best_mask = _local_search_refine(
                eligible_items,
                bucket_mask,
                target_min,
                target_max,
                max_k,
                time.perf_counter() + 0.05,
            )
        else:
            bitset_mask = _solve_exact_bitset_fallback(
                eligible_items, target_min, target_max, max_k
            )
            if bitset_mask is not None:
                algorithm_used = "bitset_local_search"
                best_mask = _local_search_refine(
                    eligible_items,
                    bitset_mask,
                    target_min,
                    target_max,
                    max_k,
                    time.perf_counter() + 0.05,
                )

        if best_mask is not None and is_exact_regime:
            exact_mask = _solve_exact_branch_and_bound(
                eligible_items,
                target_min,
                target_max,
                max_k,
                incumbent_mask=best_mask,
                budget_ms=search_budget_ms,
            )
            if exact_mask is not None:
                best_mask = exact_mask
                algorithm_used = "exact"

    if best_mask is None:
        raise _diagnose_unsatisfiable(
            candidates_retrieved=candidates_retrieved,
            playable_videos=playable_videos,
            lang_results=lang_results,
            eligible_items=eligible_items,
            constraints=constraints,
            unavailable_or_live_count=unavailable_or_live_count,
            language_mismatch_count=language_mismatch_count,
            language_missing_count=language_missing_count,
            over_max_video_count=over_max_video_count,
        )

    chosen_candidates = [eligible_items[idx] for idx in _decode_mask_indices(best_mask)]
    chosen_candidates.sort(key=lambda c: (-c.scaled_score, c.video.video_id))

    selected_videos = tuple(
        SelectedPlaylistVideo(
            video=item.video,
            relevance_score=item.relevance_score,
            duration_seconds=item.duration,
            audio_language_status=item.language_check.status,
            audio_language_label=item.language_check.label,
            is_audio_language_unverified=(item.language_check.status == "unverified"),
        )
        for item in chosen_candidates
    )
    total_duration_seconds = sum(item.duration_seconds for item in selected_videos)
    total_relevance_score = round(sum(item.relevance_score for item in selected_videos), 9)

    return PlaylistSolution(
        selected_videos=selected_videos,
        total_duration_seconds=total_duration_seconds,
        total_duration_human=format_duration(total_duration_seconds),
        total_relevance_score=total_relevance_score,
        target_min_seconds=target_min,
        target_max_seconds=target_max,
        candidates_retrieved=candidates_retrieved,
        candidates_eligible=n_elig,
        algorithm_used=algorithm_used,
    )
