"""Security tests asserting scrubbed fixtures, PII hygiene, and zero statistics (SEC_PII)."""

# ruff: noqa: N802
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from yt_intel_mcp.provider import FixtureYouTubeProvider

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import scrub_fixture  # noqa: E402

FIXTURES_DIR = ROOT / "tests" / "fixtures"


def test_SEC_PII_committed_json_fixtures_have_zero_statistics_tokens_or_emails() -> None:
    json_files = sorted(FIXTURES_DIR.rglob("*.json"))
    assert len(json_files) >= 6

    for json_file in json_files:
        payload = json.loads(json_file.read_text(encoding="utf-8"))
        violations = scrub_fixture.scan_payload_for_violations(payload, path=json_file.name)
        assert violations == [], f"Violations in {json_file}: {violations}"

    synthetic_dir = FIXTURES_DIR / "synthetic"
    for synth_file in sorted(synthetic_dir.glob("*.json")):
        payload = json.loads(synth_file.read_text(encoding="utf-8"))
        channel = payload.get("channel")
        if channel is not None:
            assert channel["channel_id"].startswith("UC_SYNTH_")


def test_SEC_PII_scrubber_strips_statistics_tokens_emails_and_anonymizes_ids(
    tmp_path: Path,
) -> None:
    sample_access = "ya29." + "sample_access_token_value"
    sample_refresh = "1//0g" + "SampleRefreshTokenForTest"
    sample_secret = "GOCSPX-" + "sampleClientSecret"
    sample_api_key = "AIza" + "SySampleKey_" + ("x" * 24)

    dirty_payload = {
        "part": "snippet,contentDetails,statistics,status",
        "access_token": sample_access,
        "refresh_token": sample_refresh,
        "client_secret": sample_secret,
        "items": [
            {
                "id": "vid_sample01",
                "snippet": {
                    "channelId": "UC_REAL_PERSON_9999",
                    "title": "Demo video contact real.user@gmail.com",
                    "description": f"Bearer {sample_access} key {sample_api_key}",
                },
                "statistics": {
                    "viewCount": "999999",
                    "likeCount": "42000",
                    "commentCount": "500",
                },
                "subscriberCount": "120000",
            }
        ],
    }

    dirty_path = tmp_path / "dirty.json"
    clean_path = tmp_path / "clean.json"
    dirty_path.write_text(json.dumps(dirty_payload), encoding="utf-8")

    assert scrub_fixture.main([str(dirty_path), "--check"]) == 1
    assert (
        scrub_fixture.main(
            [
                str(dirty_path),
                "-o",
                str(clean_path),
                "--map-user",
                "UC_REAL_PERSON_9999=UC_SYNTH_USER_999",
            ]
        )
        == 0
    )
    assert scrub_fixture.main([str(clean_path), "--check"]) == 0

    cleaned = json.loads(clean_path.read_text(encoding="utf-8"))
    assert cleaned["part"] == "snippet,contentDetails,status"
    assert "access_token" not in cleaned
    assert "refresh_token" not in cleaned
    assert "client_secret" not in cleaned
    item = cleaned["items"][0]
    assert "statistics" not in item
    assert "subscriberCount" not in item
    assert item["snippet"]["channelId"] == "UC_SYNTH_USER_999"
    assert "real.user@gmail.com" not in item["snippet"]["title"]
    assert "[REDACTED_EMAIL]" in item["snippet"]["title"]
    assert "ya29." not in item["snippet"]["description"]
    assert "AIza" not in item["snippet"]["description"]


@pytest.mark.anyio
async def test_SEC_PII_fixture_provider_outputs_exclude_popularity_and_secrets() -> None:
    provider = FixtureYouTubeProvider(FIXTURES_DIR)
    likes_items = await provider.list_playlist_items("LL_SYNTH_USER_001")
    outputs = {
        "videos": [asdict(v) for v in await provider.get_videos(["vid_seed_py01", "vid_notags02"])],
        "channels": [asdict(c) for c in await provider.get_channels(["UC_PUB_TECH_001"])],
        "my_channel": asdict(await provider.get_my_channel()),
        "subscriptions": [asdict(ev) for ev in await provider.list_subscriptions_mine()],
        "playlists": [asdict(pl) for pl in await provider.list_playlists_mine()],
        "likes_items": [asdict(ev) for ev in likes_items],
        "rated_likes": [asdict(v) for v in await provider.list_liked_videos_rated()],
    }
    assert scrub_fixture.scan_payload_for_violations(outputs) == []
