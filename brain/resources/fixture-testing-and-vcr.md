---
title: Fixture Playback and Secret Scrubbing for Continuous Integration
type: reference
created: 2026-11-09
tags:
  - testing
  - fixtures
  - vcr
  - security
requirements:
  - FR-8
  - TQ-5
  - NFR-SEC-3
---

# Fixture Playback and Secret Scrubbing for Continuous Integration

## Summary
Continuous integration workflows must remain deterministic, fast, and completely quota neutral. Test suites replay recorded and sanitized HTTP cassettes, blocking all outbound traffic to Google servers.

## Workflow and Cassette Management
1. **Recording Mode**:
   - Initial cassette capture runs in a local environment against live API endpoints with legitimate credentials.
2. **Automated Scrubbing**:
   - Before cassettes are committed, a scrubbing filter strips:
     - Authorization bearer tokens and client secrets.
     - User channel identifiers, replacing them with standard mock identifiers (`UC_TEST_CHANNEL_000000000`).
     - Real email addresses, IP addresses, and personal playlist titles.
3. **Synthetic User Data**:
   - Tests requiring personal user data (liked videos, subscriptions, private playlists) use purely synthetic fixtures generated programmatically, never real personal user recordings.
4. **Network Guard in CI**:
   - Continuous integration scripts block outbound socket connections to `googleapis.com`. Any unmocked API call fails the build immediately rather than silently consuming live quota.

## Maintenance
Cassettes are versioned alongside API schemas and refreshed when upstream data structures evolve.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]
- [[brain/resources/youtube-quota-costs|YouTube Quota Costs]]

