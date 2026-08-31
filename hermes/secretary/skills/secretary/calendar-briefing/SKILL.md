---
name: calendar-briefing
description: Summarize Google Calendar events for a bounded range.
version: 0.4.1
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
3. Treat the requested range as a half-open interval. Include an event when
   `event.start < range.end` and `event.end > range.start`. An ongoing event
   may start before the range and end after it; that makes it relevant rather
   than malformed. Treat an all-day event's end date as exclusive.
4. Report start, end, title, and location when present.
5. Highlight overlaps, short transitions, and preparation needs without
   inventing missing details.
6. Report connector authentication, permission, pagination, or query failures
   as coverage gaps.

## Pitfalls

- Do not claim a free period outside the queried range.
- Do not require an event to start inside the range. A bounded provider query
  can correctly return an event that overlaps the range from either side.
- Do not use a bare datetime without a timezone.
- Do not infer permission to mutate events from any briefing request.
- Do not broaden Google OAuth scopes when Calendar access is sufficient.

## Verification

- Confirm that `google-calendar` returned valid provider data for the requested
  range.
- Confirm that every reported event overlaps that range.
- Confirm that the workflow made no calendar mutation.
