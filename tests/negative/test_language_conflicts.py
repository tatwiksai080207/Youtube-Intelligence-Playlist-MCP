"""Negative tests for MF-09 spoken vs text language conflicts (NT_LANG, FR-5.1a, INV-10)."""

# ruff: noqa: N802
from __future__ import annotations

import pytest

from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import VideoMeta
from yt_intel_mcp.playlist import (
    UNVERIFIED_AUDIO_LANGUAGE_LABEL,
    build_playlist_constraints,
    evaluate_video_audio_language,
    filter_videos_by_language,
    is_video_language_eligible,
)


def _video(
    video_id: str,
    *,
    default_audio_language: str | None,
    default_language: str | None,
) -> VideoMeta:
    return VideoMeta(
        video_id=video_id,
        title=f"Title {video_id}",
        duration_seconds=600,
        default_audio_language=default_audio_language,
        default_language=default_language,
    )


def test_NT_LANG_conflicting_default_language_never_proves_spoken_language() -> None:
    strict = build_playlist_constraints(
        topic="databases",
        target_total_minutes=60,
        language="en",
        allow_unknown_language=False,
    )
    permissive = build_playlist_constraints(
        topic="databases",
        target_total_minutes=60,
        language="en",
        allow_unknown_language=True,
    )

    # Video metadata tagged English for title/description, but spoken audio is French
    french_audio_english_text = _video(
        "V_CONFLICT_FR",
        default_audio_language="fr",
        default_language="en",
    )
    # Video metadata tagged English for title/description, with NO spoken audio metadata
    missing_audio_english_text = _video(
        "V_MISSING_EN_TEXT",
        default_audio_language=None,
        default_language="en-US",
    )
    # Video metadata tagged French for text, while actual spoken audio IS English
    english_audio_french_text = _video(
        "V_EN_AUDIO_FR_TEXT",
        default_audio_language="en-GB",
        default_language="fr",
    )

    # Known audio mismatch is excluded even when allow_unknown_language=True and defaultLanguage=en
    for cfg in (strict, permissive):
        res = evaluate_video_audio_language(
            french_audio_english_text,
            cfg.language,
            allow_unknown_language=cfg.allow_unknown_language,
        )
        assert res.eligible is False
        assert res.status == "mismatch"
        assert is_video_language_eligible(french_audio_english_text, cfg) is False

    # Missing audio is excluded by default even if defaultLanguage matches requested language
    missing_res = evaluate_video_audio_language(
        missing_audio_english_text,
        strict.language,
        allow_unknown_language=strict.allow_unknown_language,
    )
    assert missing_res.eligible is False
    assert missing_res.status == "missing_excluded"

    # Missing audio is allowed ONLY when allow_unknown_language=True, labelled unverified
    missing_opt_in = evaluate_video_audio_language(
        missing_audio_english_text,
        permissive.language,
        allow_unknown_language=permissive.allow_unknown_language,
    )
    assert missing_opt_in.eligible is True
    assert missing_opt_in.status == "unverified"
    assert missing_opt_in.label == UNVERIFIED_AUDIO_LANGUAGE_LABEL

    # English spoken audio passes despite French text metadata
    assert is_video_language_eligible(english_audio_french_text, strict) is True

    eligible, excluded = filter_videos_by_language(
        [french_audio_english_text, missing_audio_english_text, english_audio_french_text],
        strict,
    )
    assert [v.video_id for v, _ in eligible] == ["V_EN_AUDIO_FR_TEXT"]
    assert [v.video_id for v, _ in excluded] == ["V_CONFLICT_FR", "V_MISSING_EN_TEXT"]


def test_NT_LANG_rejects_invalid_requested_language_tag() -> None:
    sample = _video("V1", default_audio_language="en", default_language="en")
    with pytest.raises(ToolError) as exc_info:
        evaluate_video_audio_language(sample, "invalid language tag")
    assert exc_info.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc_info.value.details["field"] == "language"
