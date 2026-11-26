"""Pure deterministic TF-IDF vectorization, cosine similarity, and query term extraction."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence

from yt_intel_mcp.sanitize import sanitize_text

__all__ = [
    "DEFAULT_DESCRIPTION_PREFIX_LENGTH",
    "ENGLISH_STOP_WORDS",
    "SparseVector",
    "TfidfVectorizer",
    "build_search_query",
    "cosine_similarity",
    "extract_key_terms",
    "score_texts_cosine",
    "shared_matched_terms",
    "tokenize_tags",
    "tokenize_text",
]

SparseVector = dict[str, float]
DEFAULT_DESCRIPTION_PREFIX_LENGTH = 500
_TOKEN_RE = re.compile(r"[a-z0-9]+")

ENGLISH_STOP_WORDS: frozenset[str] = frozenset(
    {
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "also",
        "am",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "doing",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "itself",
        "just",
        "me",
        "more",
        "most",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "now",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "she",
        "should",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)


def tokenize_text(
    text: str,
    *,
    max_length: int | None = None,
    remove_stopwords: bool = True,
) -> tuple[str, ...]:
    """Sanitize, lowercase, strip stopwords, and extract tokens >= 2 characters (ADR-0003)."""
    if not text:
        return ()
    sanitized = (
        sanitize_text(text) if max_length is None else sanitize_text(text, max_length=max_length)
    )
    cleaned = sanitized.lower()
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(cleaned):
        if len(token) < 2:
            continue
        if remove_stopwords and token in ENGLISH_STOP_WORDS:
            continue
        tokens.append(token)
    return tuple(tokens)


def tokenize_tags(tags: Sequence[str]) -> tuple[str, ...]:
    """Tokenize creator metadata tags independently without merging adjacent tags."""
    tokens: list[str] = []
    for tag in tags:
        tokens.extend(tokenize_text(tag))
    return tuple(tokens)


class TfidfVectorizer:
    """Sublinear TF and smoothed IDF sparse L2-normalized vectorizer (ADR-0003)."""

    def __init__(self) -> None:
        self._num_docs: int = 0
        self._idf: dict[str, float] = {}

    @property
    def num_docs(self) -> int:
        """Number of documents included in the fitted corpus."""
        return self._num_docs

    @property
    def idf(self) -> Mapping[str, float]:
        """Smoothed inverse document frequency weight per vocabulary term."""
        return self._idf

    def fit(self, documents: Sequence[Sequence[str]]) -> TfidfVectorizer:
        """Compute smoothed IDF weights across all non-empty or empty token documents."""
        if not documents:
            raise ValueError("Cannot fit TfidfVectorizer on an empty corpus.")

        doc_freq: Counter[str] = Counter()
        for doc in documents:
            doc_freq.update(set(doc))

        n_docs = len(documents)
        self._num_docs = n_docs
        self._idf = {
            term: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0 for term, df in doc_freq.items()
        }
        return self

    def transform(self, tokens: Sequence[str]) -> SparseVector:
        """Transform a token sequence into an L2-normalized sublinear TF-IDF vector."""
        if self._num_docs == 0:
            raise ValueError("TfidfVectorizer must be fitted before transform().")
        if not tokens:
            return {}

        counts = Counter(tokens)
        oov_idf = math.log(1.0 + self._num_docs) + 1.0
        raw_weights: dict[str, float] = {}
        squared_norm = 0.0
        for term, count in counts.items():
            tf = 1.0 + math.log(count)
            idf_weight = self._idf.get(term, oov_idf)
            weight = tf * idf_weight
            raw_weights[term] = weight
            squared_norm += weight * weight

        if squared_norm <= 0.0:
            return {}
        norm = math.sqrt(squared_norm)
        return {term: weight / norm for term, weight in raw_weights.items()}

    def fit_transform(self, documents: Sequence[Sequence[str]]) -> list[SparseVector]:
        """Fit IDF weights and return normalized sparse vectors aligned to documents."""
        self.fit(documents)
        return [self.transform(doc) for doc in documents]


def cosine_similarity(vec_a: Mapping[str, float], vec_b: Mapping[str, float]) -> float:
    """Compute cosine similarity in `[0.0, 1.0]` between two non-negative sparse vectors."""
    if not vec_a or not vec_b:
        return 0.0

    small, large = (vec_a, vec_b) if len(vec_a) <= len(vec_b) else (vec_b, vec_a)
    dot = 0.0
    for term, weight_a in small.items():
        weight_b = large.get(term)
        if weight_b is not None:
            dot += weight_a * weight_b
    if dot <= 0.0:
        return 0.0

    norm_a_sq = sum(val * val for val in vec_a.values())
    norm_b_sq = sum(val * val for val in vec_b.values())
    if norm_a_sq <= 0.0 or norm_b_sq <= 0.0:
        return 0.0

    cosine = dot / math.sqrt(norm_a_sq * norm_b_sq)
    return min(1.0, max(0.0, cosine))


def score_texts_cosine(
    query_tokens: Sequence[str],
    candidate_docs: Sequence[Sequence[str]],
) -> list[float]:
    """Fit a corpus over query plus candidates and return `[0.0, 1.0]` cosine similarities."""
    if not candidate_docs:
        return []
    if not query_tokens:
        return [0.0] * len(candidate_docs)

    vectors = TfidfVectorizer().fit_transform([query_tokens, *candidate_docs])
    query_vec = vectors[0]
    return [cosine_similarity(query_vec, cand_vec) for cand_vec in vectors[1:]]


def extract_key_terms(documents: Sequence[Sequence[str]], *, max_terms: int = 8) -> tuple[str, ...]:
    """Extract deterministic top TF-IDF terms across a token corpus for search queries."""
    if max_terms <= 0:
        raise ValueError(f"max_terms must be positive, got {max_terms}.")
    if not documents or all(not doc for doc in documents):
        return ()

    vectors = TfidfVectorizer().fit_transform(documents)
    aggregated: dict[str, float] = {}
    for vector in vectors:
        for term, weight in vector.items():
            aggregated[term] = aggregated.get(term, 0.0) + weight

    ranked = sorted(aggregated.items(), key=lambda item: (-item[1], item[0]))
    return tuple(term for term, _ in ranked[:max_terms])


def build_search_query(title: str, tags: Sequence[str] = (), *, max_terms: int = 5) -> str:
    """Build a concise deterministic search query from objective title and tags (FR-1.2)."""
    if max_terms <= 0:
        raise ValueError(f"max_terms must be positive, got {max_terms}.")
    title_tokens = tokenize_text(title)
    tag_tokens = tokenize_tags(tags)

    ordered: list[str] = []
    seen: set[str] = set()
    for token in (*title_tokens, *tag_tokens):
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
        if len(ordered) >= max_terms:
            break
    return " ".join(ordered)


def shared_matched_terms(
    tokens_a: Sequence[str],
    tokens_b: Sequence[str],
    weights: Mapping[str, float] | None = None,
    *,
    limit: int = 5,
) -> tuple[str, ...]:
    """Return top deterministic overlapping keywords ordered by importance weight."""
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}.")
    overlap = set(tokens_a) & set(tokens_b)
    if not overlap:
        return ()

    counts_a = Counter(tokens_a)
    counts_b = Counter(tokens_b)

    def _rank_key(term: str) -> tuple[float, str]:
        if weights is not None and term in weights:
            return (-weights[term], term)
        score = float(min(counts_a[term], counts_b[term]))
        return (-score, term)

    return tuple(sorted(overlap, key=_rank_key)[:limit])
