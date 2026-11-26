"""Negative tests for private, deleted, and missing video handling (NT_VID, FR-1.4)."""

# ruff: noqa: N802
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from yt_intel_mcp.config import QuotaConfig
from yt_intel_mcp.errors import ErrorCode, ToolError
from yt_intel_mcp.models import QuotaUsed
from yt_intel_mcp.provider import FixtureYouTubeProvider
from yt_intel_mcp.quota.ledger import PersistentQuotaLedger
from yt_intel_mcp.store import SQLiteStore
from yt_intel_mcp.tools.get_video_details import execute_get_video_details


def _write_unavailable_fixtures(root: Path) -> Path:
    public = root / "public"
    synthetic = root / "synthetic"
    public.mkdir(parents=True)
    synthetic.mkdir(parents=True)
    videos = {
        "videos": [
            {
                "video_id": "privVid0003",
                "title": "Private Draft Lecture",
                "description": "Private recording unavailable to callers.",
                "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
                "channel_title": "Systems Craft",
                "published_at": "2026-08-01T10:00:00Z",
                "tags": ["python"],
                "category_id": "27",
                "category_name": "Education",
                "duration_seconds": 480,
                "default_audio_language": "en",
                "default_language": "en",
                "live_broadcast_content": "none",
                "is_embeddable": False,
                "privacy_status": "private",
                "is_age_restricted": False,
                "is_available": False,
            },
            {
                "video_id": "delVid00004",
                "title": "Deleted Video",
                "description": "",
                "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
                "channel_title": "Systems Craft",
                "published_at": "2026-07-01T10:00:00Z",
                "tags": [],
                "category_id": "27",
                "category_name": "Education",
                "duration_seconds": 300,
                "default_audio_language": "en",
                "default_language": "en",
                "live_broadcast_content": "none",
                "is_embeddable": False,
                "privacy_status": "deleted",
                "is_age_restricted": False,
                "is_available": False,
            },
        ]
    }
    (public / "videos.json").write_text(json.dumps(videos), encoding="utf-8")
    (public / "channels.json").write_text(json.dumps({"channels": []}), encoding="utf-8")
    (public / "searches.json").write_text(
        json.dumps({"video_queries": {}, "channel_queries": {}}),
        encoding="utf-8",
    )
    (public / "categories.json").write_text(json.dumps({"US": {}}), encoding="utf-8")
    (synthetic / "default_user.json").write_text(
        json.dumps({"has_channel": False, "subscriptions": [], "playlists": []}),
        encoding="utf-8",
    )
    return root


@pytest.mark.parametrize("video_id", ["privVid0003", "delVid00004", "missVid0099"])
def test_NT_VID_private_deleted_and_missing_videos_raise_unavailable(
    tmp_path: Path,
    video_id: str,
) -> None:
    fixtures_dir = _write_unavailable_fixtures(tmp_path / "fixtures")
    store = SQLiteStore(tmp_path / "yt_intel.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig())
    provider = FixtureYouTubeProvider(fixtures_dir, quota_guard=ledger)

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(
            execute_get_video_details(
                {"video_id": video_id},
                provider=provider,
                quota_guard=ledger,
            )
        )
    assert exc_info.value.code is ErrorCode.VIDEO_UNAVAILABLE
    assert exc_info.value.quota_used == QuotaUsed(units=1, search_calls=0)


def test_NT_VID_invalid_video_id_rejects_pre_quota_with_zero_calls(tmp_path: Path) -> None:
    fixtures_dir = _write_unavailable_fixtures(tmp_path / "fixtures")
    store = SQLiteStore(tmp_path / "yt_intel.db")
    ledger = PersistentQuotaLedger(store, QuotaConfig())
    provider = FixtureYouTubeProvider(fixtures_dir, quota_guard=ledger)

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(
            execute_get_video_details(
                {"video_id": "https://evil.example.com/watch?v=dQw4w9WgXcQ"},
                provider=provider,
                quota_guard=ledger,
            )
        )
    assert exc_info.value.code is ErrorCode.INVALID_ARGUMENT
    assert exc_info.value.quota_used == QuotaUsed(units=0, search_calls=0)
    assert provider.calls == []
    assert ledger.status().units_used == 0
