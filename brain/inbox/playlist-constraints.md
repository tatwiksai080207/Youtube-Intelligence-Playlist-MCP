---
title: Playlist Duration and Spoken Language Constraints
type: reference
status: inbox
authors:
  - Mohammed Farhan
created: 2026-11-25
updated: 2026-11-25
tags:
  - playlist
  - constraints
  - duration
  - language
requirements:
  - FR-5.1
  - FR-5.1a
  - FR-5.2
  - SB-1
  - SB-6
issues:
  - "#7"
prs: []
sources:
  - "Final_SRS_Submission.pdf v1.0, section 4.5 (checked 2026-11-25)"
  - "YouTube Data API v3 video resource audio language: https://developers.google.com/youtube/data/reference/rest/v3/videos#snippet.defaultAudioLanguage (checked 2026-11-25)"
  - "YouTube Data API v3 video resource duration: https://developers.google.com/youtube/data/reference/rest/v3/videos#contentDetails.duration (checked 2026-11-25)"
---

# Playlist Duration and Spoken Language Constraints

## Summary

FR-5.1 turns the request into a topic, a target duration with an inclusive window, a per-video maximum duration, an upper bound on the number of videos, and an optional spoken language. FR-5.1a defines eligibility using YouTube's default audio language metadata.

## Duration and count

For target `T` and tolerance as a fraction `t`, the permitted total is `[T × (1 − t), T]`. The default tolerance is 5%. At 120 minutes, 114:00 and 120:00 are valid, while 113:59 and 120:01 fall outside the window. Use the ISO 8601 value in `contentDetails.duration` on a common time scale for both bounds and each candidate. A video exactly at `max_video_minutes` passes the per-video duration check. Fewer than `max_videos` is valid if every other constraint holds.

## Spoken language

When the user requests a language, compare its primary language subtag with the primary subtag of `snippet.defaultAudioLanguage`. YouTube uses `snippet.defaultLanguage` for title and description text. That text field provides no spoken-language evidence.

| Requested language | Default audio language | Result |
|---|---|---|
| `en` | `en-GB` | Eligible on the language check |
| `en` | `fr` | Excluded, even if the title and description are tagged `en` |
| `en` | Missing | Excluded by default |
| `en` with `allow_unknown_language=true` | Missing | Eligible and labelled **Audio language unverified** if selected |

The opt-in applies only to unknown audio language. A known mismatch remains excluded. When the user omits the language constraint, the solver does not filter on spoken language.

## Selection and verification targets

Among retrieved candidates, the solver maximizes topic relevance subject to every constraint. If no combination qualifies, `CONSTRAINTS_UNSATISFIABLE` reports the number of candidates retrieved and the binding constraint. A broader search must disclose its cost, and a named relaxation requires the user's choice.

- `UT_SOLV_WINDOW` covers both endpoints, adjacent out-of-window totals, and equality at the per-video maximum.
- `UT_LANG` and `NT_LANG` cover primary-subtag matching, conflicting text and audio languages, and the explicit unknown-language opt-in.

## Related notes

- [[brain/resources/knapsack-constraint-solving|Knapsack Constraint Solving]]
- [[brain/inbox/mcp-elicitation-confirmation|Trusted confirmation]]
- [[brain/inbox/partial-playlist-outcomes|Partial playlist outcomes]]
