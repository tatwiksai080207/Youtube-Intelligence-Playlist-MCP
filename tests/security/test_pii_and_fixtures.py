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


def test_SEC_PII_auth_revoke_deletes_tokens_and_personal_cache_but_retains_quota(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime, timedelta

    from yt_intel_mcp.auth import YOUTUBE_READONLY_SCOPE, TokenBundle, TokenStore
    from yt_intel_mcp.cache import MetadataCache
    from yt_intel_mcp.models import CostEstimate
    from yt_intel_mcp.quota import PersistentQuotaLedger
    from yt_intel_mcp.store import SQLiteStore
    from yt_intel_mcp.tools import execute_get_auth_status

    class _MemKeyring:
        def __init__(self) -> None:
            self.items: dict[tuple[str, str], str] = {}

        def get_password(self, service_name: str, username: str) -> str | None:
            return self.items.get((service_name, username))

        def set_password(self, service_name: str, username: str, password: str) -> None:
            self.items[(service_name, username)] = password

        def delete_password(self, service_name: str, username: str) -> None:
            self.items.pop((service_name, username), None)

    data_dir = tmp_path / "revoke_dir"
    store = SQLiteStore(data_dir / "yt_intel.db")
    ledger = PersistentQuotaLedger(store)
    ledger.charge(CostEstimate(units=25, search_calls=2, operation="prior"))
    cache = MetadataCache(store)
    cache.put("videos:item:vid_seed_py01", "videos", {"video_id": "vid_seed_py01"})
    cache.put("user_lists:subscriptions_mine:50", "user_lists", [{"video_id": "v1"}])
    with store.transaction(immediate=True) as conn:
        conn.execute(
            """
            INSERT INTO first_observed (source, item_id, first_observed_utc)
            VALUES ('liked_video', 'vid_seed_py01', '2026-11-26T10:00:00Z');
            """
        )

    kr = _MemKeyring()
    now = datetime(2026, 11, 26, 15, 0, tzinfo=UTC)
    bundle = TokenBundle(
        access_token="ya29." + "revoke_test_access_token",
        refresh_token="1//0g" + "revoke_test_refresh_token",
        scopes=(YOUTUBE_READONLY_SCOPE,),
        expires_at_utc=now + timedelta(hours=1),
        issued_at_utc=now,
        channel_id="UC_SYNTH_USER_001",
    )

    # Save encrypted file first, then also populate keyring to verify revoke clears both.
    file_store = TokenStore(data_dir, use_system_keyring=False)
    file_store.save_bundle(bundle)
    assert file_store.tokens_path.is_file()

    kr_store = TokenStore(data_dir, keyring_backend=kr)
    kr.set_password(kr_store.service_name, kr_store.account_key, "serialized")

    result = kr_store.revoke(store=store)
    assert result.keyring_cleared is True
    assert result.encrypted_file_deleted is True
    assert result.personal_cache_deleted == 1
    assert result.first_observed_deleted == 1

    assert not file_store.tokens_path.exists()
    assert kr.items == {}
    assert kr_store.load_bundle() is None
    assert execute_get_auth_status(kr_store)["data"]["authenticated"] is False

    # Public metadata cache and daily quota ledger remain intact (ADR-0006).
    assert cache.get("videos:item:vid_seed_py01") == {"video_id": "vid_seed_py01"}
    assert cache.get("user_lists:subscriptions_mine:50") is None
    assert ledger.status().units_used == 25
    assert ledger.status().search_calls_used == 2
