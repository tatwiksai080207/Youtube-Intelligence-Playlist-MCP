"""Unit tests for MF-09 spoken audio-language validator (UT_LANG, FR-5.1a, INV-10)."""

# ruff: noqa: N802
from __future__ import annotations

import pytest

from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.playlist import (
    UNVERIFIED_AUDIO_LANGUAGE_LABEL,
    build_playlist_constraints,
    evaluate_video_audio_language,
    filter_videos_by_language,
    is_video_language_eligible,
    primary_language_subtag,
)


def _video(
    video_id: str,
    *,
    default_audio_language: str | None,
    default_language: str | None = None,
) -> VideoMeta:
    return VideoMeta(
        video_id=video_id,
        title=f"Video {video_id}",
        duration_seconds=600,
        default_audio_language=default_audio_language,
        default_language=default_language,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("en", "en"),
        ("en-GB", "en"),
        ("EN-us", "en"),
        ("pt-BR", "pt"),
        ("zh-Hans", "zh"),
        ("fil", "fil"),
        ("  hi_IN  ", "hi"),
        (None, None),
        ("", None),
        ("   ", None),
        ("123", None),
        ("english", None),
    ],
)
def test_UT_LANG_primary_language_subtag_extraction(raw: str | None, expected: str | None) -> None:
    assert primary_language_subtag(raw) == expected


def test_UT_LANG_matches_default_audio_language_by_primary_subtag() -> None:
    constraints = build_playlist_constraints(
        topic="async python",
        target_total_minutes=60,
        language="en-US",
    )

    exact = _video("V_EN", default_audio_language="en")
    uk = _video("V_EN_GB", default_audio_language="en-GB")
    au = _video("V_EN_AU", default_audio_language="EN-au")
    other = _video("V_FR", default_audio_language="fr")
    three_letter = _video("V_ENO", default_audio_language="eno")

    res_exact = evaluate_video_audio_language(exact, constraints.language)
    res_uk = evaluate_video_audio_language(uk, constraints.language)
    res_au = evaluate_video_audio_language(au, constraints.language)
    res_other = evaluate_video_audio_language(other, constraints.language)
    res_eno = evaluate_video_audio_language(three_letter, constraints.language)

    assert res_exact.eligible is True
    assert res_exact.status == "verified"
    assert res_uk.eligible is True
    assert res_uk.primary_subtag == "en"
    assert res_au.eligible is True
    assert res_other.eligible is False
    assert res_other.status == "mismatch"
    assert res_eno.eligible is False
    assert res_eno.status == "mismatch"


def test_UT_LANG_allow_unknown_language_opt_in_labels_missing_audio_only() -> None:
    strict_constraints = build_playlist_constraints(
        topic="systems",
        target_total_minutes=60,
        language="en",
        allow_unknown_language=False,
    )
    opt_in_constraints = build_playlist_constraints(
        topic="systems",
        target_total_minutes=60,
        language="en",
        allow_unknown_language=True,
    )

    known_en = _video("V_EN", default_audio_language="en-GB")
    missing_none = _video("V_NONE", default_audio_language=None)
    missing_blank = _video("V_BLANK", default_audio_language="   ")
    undetermined = _video("V_UND", default_audio_language="und")
    known_es = _video("V_ES", default_audio_language="es")

    assert is_video_language_eligible(missing_none, strict_constraints) is False
    assert is_video_language_eligible(missing_blank, strict_constraints) is False
    assert is_video_language_eligible(undetermined, strict_constraints) is False

    eligible, excluded = filter_videos_by_language(
        [known_en, missing_none, missing_blank, undetermined, known_es],
        opt_in_constraints,
    )
    assert [v.video_id for v, _ in eligible] == ["V_EN", "V_NONE", "V_BLANK", "V_UND"]
    assert [v.video_id for v, _ in excluded] == ["V_ES"]

    for video, check in eligible:
        if video.video_id == "V_EN":
            assert check.status == "verified"
        else:
            assert check.status == "unverified"
            assert check.label == UNVERIFIED_AUDIO_LANGUAGE_LABEL
            assert check.label == "Audio language unverified"

    assert excluded[0][1].status == "mismatch"


def test_UT_LANG_no_language_filter_accepts_all_videos() -> None:
    constraints = build_playlist_constraints(topic="compilers", target_total_minutes=45)
    videos = [
        _video("V1", default_audio_language="fr"),
        _video("V2", default_audio_language=None),
    ]
    eligible, excluded = filter_videos_by_language(videos, constraints)
    assert len(eligible) == 2
    assert excluded == []
    assert eligible[0][1].status == "not_filtered"
    assert eligible[0][1].label == "Audio language: fr"
    assert eligible[1][1].status == "not_filtered"
    assert eligible[1][1].label == UNVERIFIED_AUDIO_LANGUAGE_LABEL
