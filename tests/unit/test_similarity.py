"""Unit tests for pure TF-IDF vectorization and cosine similarity engine (UT_SIM, FR-1.2)."""

# ruff: noqa: N802
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from yt_intel_mcp.similarity import (
    DEFAULT_DESCRIPTION_PREFIX_LENGTH,
    TfidfVectorizer,
    build_search_query,
    cosine_similarity,
    extract_key_terms,
    score_texts_cosine,
    shared_matched_terms,
    tokenize_tags,
    tokenize_text,
)

FORBIDDEN_POPULARITY_AND_HTTP = {
    "httpx",
    "httpx2",
    "httpcore",
    "httpcore2",
    "requests",
    "aiohttp",
    "google",
    "view_count",
    "like_count",
    "subscriber_count",
    "statistics",
}


def test_UT_SIM_tokenize_strips_urls_stopwords_punctuation_and_short_tokens() -> None:
    raw = "The Quick Python 3.11 & AsyncIO Event-Loop! Visit https://evil.example.com/a?b=1 c x"
    tokens = tokenize_text(raw)
    assert tokens == ("quick", "python", "11", "asyncio", "event", "loop", "visit")

    long_desc = "asyncio " * 120
    capped = tokenize_text(long_desc, max_length=DEFAULT_DESCRIPTION_PREFIX_LENGTH)
    assert len(capped) < 120

    assert tokenize_text("") == ()
    assert tokenize_tags(["Python 3.11", "Async IO", "the"]) == ("python", "11", "async", "io")


def test_UT_SIM_tfidf_vectorizer_idf_rarity_and_cosine_bounds() -> None:
    corpus = [
        tokenize_text("Python asyncio event loops and structured concurrency"),
        tokenize_text("Python asyncio task groups and coroutines"),
        tokenize_text("Python SQLite WAL mode storage internals"),
        tokenize_text("Sourdough baking fermentation chemistry"),
    ]
    vec = TfidfVectorizer().fit(corpus)
    assert vec.num_docs == 4
    assert vec.idf["sourdough"] > vec.idf["python"]

    vectors = [vec.transform(doc) for doc in corpus]
    assert cosine_similarity(vectors[0], vectors[0]) == pytest.approx(1.0)
    assert cosine_similarity(vectors[0], vectors[3]) == 0.0
    sim_0_1 = cosine_similarity(vectors[0], vectors[1])
    sim_0_2 = cosine_similarity(vectors[0], vectors[2])
    assert 0.0 < sim_0_2 < sim_0_1 < 1.0


def test_UT_SIM_sublinear_tf_dampens_keyword_spam() -> None:
    doc_normal = tokenize_text("asyncio coroutines tasks")
    doc_spam = tokenize_text(("asyncio " * 20) + "coroutines tasks")
    vec = TfidfVectorizer().fit([doc_normal, doc_spam])

    w_normal = vec.transform(doc_normal)
    w_spam = vec.transform(doc_spam)
    ratio = w_spam["asyncio"] / w_normal["asyncio"]
    assert ratio < 5.0


def test_UT_SIM_empty_and_zero_vector_edge_cases() -> None:
    assert cosine_similarity({}, {"python": 1.0}) == 0.0
    assert cosine_similarity({}, {}) == 0.0
    assert cosine_similarity({"a": 0.0}, {"a": 1.0}) == 0.0
    assert score_texts_cosine((), [("python",)]) == [0.0]
    assert score_texts_cosine(("python",), []) == []

    vec = TfidfVectorizer().fit([("python", "asyncio"), ()])
    assert vec.transform(()) == {}


def test_UT_SIM_query_and_matched_term_helpers_are_deterministic() -> None:
    docs = [
        tokenize_text("Rust systems programming and ownership model"),
        tokenize_text("Rust zero cost abstractions and systems design"),
    ]
    scores = score_texts_cosine(tokenize_text("Rust systems design"), docs)
    assert len(scores) == 2
    assert scores[1] > scores[0] > 0.0

    key_terms = extract_key_terms(docs, max_terms=4)
    assert len(key_terms) == 4
    assert "rust" in key_terms
    assert "systems" in key_terms
    assert extract_key_terms([(), ()]) == ()

    query = build_search_query(
        "Python Asyncio Internals & Loops", tags=["Concurrency", "Systems"], max_terms=4
    )
    assert query == "python asyncio internals loops"
    assert build_search_query("", []) == ""

    overlap = shared_matched_terms(
        ("python", "asyncio", "raft", "sqlite"),
        ("raft", "python", "consensus"),
        weights={"raft": 0.9, "python": 0.4},
        limit=2,
    )
    assert overlap == ("raft", "python")
    assert shared_matched_terms(("a",), ("b",)) == ()


def test_UT_SIM_text_similarity_guards_and_domain_isolation() -> None:
    with pytest.raises(ValueError, match="empty corpus"):
        TfidfVectorizer().fit([])
    with pytest.raises(ValueError, match="fitted"):
        TfidfVectorizer().transform(("python",))
    with pytest.raises(ValueError, match="max_terms"):
        extract_key_terms([("python",)], max_terms=0)
    with pytest.raises(ValueError, match="max_terms"):
        build_search_query("python", max_terms=0)
    with pytest.raises(ValueError, match="limit"):
        shared_matched_terms(("a",), ("a",), limit=0)

    source = Path(__file__).resolve().parents[2] / "src" / "yt_intel_mcp" / "similarity" / "text.py"
    raw = source.read_text(encoding="utf-8")
    tree = ast.parse(raw)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(FORBIDDEN_POPULARITY_AND_HTTP)
    for forbidden in (
        "view_count",
        "viewCount",
        "like_count",
        "likeCount",
        "subscriber_count",
        "subscriberCount",
    ):
        assert forbidden not in raw
