# ADR-0012: Use structured native secretary clients

- Status: Superseded
- Date: 2026-08-24

In the context of a macOS Hermes secretary that must read the calendar already
visible to Apple Calendar, manage every configured mail account, and summarize
authenticated X sources from unattended routines, facing duplicate CalDAV
state, fragile Mail automation, and non-deterministic public X discovery, we
decided for a revision-pinned EventKit `ical`, Himalaya 2 with explicit
multi-account coverage, and the official `xurl` client, and against
vdirsyncer/khal, AppleScript or Mail database adapters, and Hermes `x_search`,
to obtain provider-aligned structured output suitable for verification and
cron, accepting separate local authentication for each mail provider and X.
