---
name: calendar-briefing
description: Summarize Google Calendar events for a bounded range.
version: 0.4.0
author: furedea
license: MIT
platforms: [macos]
metadata:
    hermes:
        tags: [calendar, google-calendar, briefing]
        related_skills: [google-calendar, morning-briefing]
---

# Calendar Briefing

Summarize events retrieved by the local `google-calendar` connector. This
workflow interprets event facts but does not own provider access or mutations.

## When to Use

- The user asks about today's schedule or a bounded date range.
- A morning briefing needs its calendar section.

## Procedure

1. Load `google-calendar`; it owns authentication, query construction, data
   handling, and the read-only boundary.
2. Request the narrowest date range and smallest useful result limit from that
   connector.
3. Report start, end, title, and location when present.
4. Highlight overlaps, short transitions, and preparation needs without
   inventing missing details.
5. Report connector authentication, permission, pagination, or query failures
   as coverage gaps.

## Pitfalls

- Do not claim a free period outside the queried range.
- Do not use a bare datetime without a timezone.
- Do not infer permission to mutate events from any briefing request.
- Do not broaden Google OAuth scopes when Calendar access is sufficient.

## Verification

- Confirm that `google-calendar` returned valid provider data for the requested
  range.
- Confirm that every reported event falls within that range.
- Confirm that the workflow made no calendar mutation.
