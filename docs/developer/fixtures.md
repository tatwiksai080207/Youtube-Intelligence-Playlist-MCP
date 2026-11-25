# Fixture Testing, Recording, and Scrubbing Rules (`TQ-5`, `NFR-4`, `NFR-7`)

Pull Request CI runs strictly in offline fixture mode (`YT_INTEL_PROVIDER=fixture`) so every automated check consumes **zero live YouTube Data API quota** and never depends on network access or OAuth secrets.

## 1. Directory Layout

```text
tests/fixtures/
├── validators/          # Markdown fixtures for validate_brain.py / validate_skills.py
└── ...                  # Scoped JSON fixtures for FixtureYouTubeProvider (added in SR-08+)
```

`AppConfig.fixture_dir` defaults to `tests/fixtures` and may be overridden per test or run using `YT_INTEL_FIXTURE_DIR`.

## 2. Objective Metadata & Scrubbing Rules (`INV-01`, `NFR-4`, `NFR-7`)

Before committing any fixture JSON under `tests/fixtures/`:
1. **No secrets or credentials:** Never include OAuth `client_secret`, `refresh_token`, `access_token`, API keys, bearer headers, cookies, or email addresses (`gitleaks` CI gate).
2. **No popularity statistics (`INV-01`):** Omit the YouTube `statistics` part (`viewCount`, `likeCount`, `subscriberCount`, `commentCount`, `videoCount`) from all recorded fixtures. Fixtures carry only objective snippet, contentDetails, status, and topicDetails fields mapped into `VideoMeta`, `ChannelMeta`, `SearchHit`, `PlaylistSummary`, and `UserEvent`.
3. **Synthetic user personas only (`NFR-7`):** Personal library fixtures (subscriptions, likes playlist items, rated likes, user-owned playlists) must use anonymized synthetic channel IDs (for example `UC_SYNTH_USER_001`) and fabricated timestamps — never dump real personal watch, like, or subscription histories.
4. **Canonical timestamp coverage:** Synthetic user-library fixtures should represent `dated` events (`snippet.publishedAt`), `undated` likes (`videos.list?myRating=like`), multiple ISO 8601 durations covering `<240s` (short), `240s..1200s` (medium), `>1200s` (long), live streams, and `defaultAudioLanguage` vs `defaultLanguage` mismatches.
5. **Simulated upstream errors:** Fixture error cases must mirror `SRS Section 5` (`quotaExceeded`, `rateLimitExceeded` / HTTP `429`, `videoNotFound`, `youtubeSignupRequired`, `insufficientPermissions`, `invalid_grant`, `forbidden`) without exposing raw response auth headers.

## 3. Running Fixture CI vs Live Smoke Tests (`NFR-2`)

- **Default / PR CI (zero quota):**
  ```bash
  YT_INTEL_PROVIDER=fixture pytest -m "not live" --cov=yt_intel_mcp --cov-fail-under=85
  ```
- **Opt-in live smoke tests (`@pytest.mark.live`):**
  - Strictly excluded from PR CI (`-m "not live"`).
  - Enforces a hard ceiling of `300` quota units and `10` `search.list` calls per run (`AppConfig.live_tests` in `src/yt_intel_mcp/config.py`).
  - Requires explicit developer consent, a non-committed local OAuth client config outside git, and `YT_INTEL_PROVIDER=live`.
