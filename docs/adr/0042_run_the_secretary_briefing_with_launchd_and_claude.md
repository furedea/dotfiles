# ADR-0042: Run the secretary briefing with launchd and claude -p

- Status: Accepted
- Date: 2026-11-04
- Supersedes: ADR-0022

In the context of the morning briefing losing its Hermes gateway (removed in Issue #378), facing a
resident process, Slack delivery, and a Skill store tied to a Hermes profile, we decided for a
Home Manager `launchd.agents.morning-briefing` that starts `claude -p` once a day at 08:00 from the
`secretary/` directory, with Skills in `secretary/.claude/skills`, a dedicated read-only
`secretary/.claude/settings.json`, state in `~/.local/state/secretary/`, delivery to one fixed
Artifact, and a notification through an Apple Reminder (iCloud syncs it to iPhone and Mac), and
against a resident gateway or desktop app, cloud scheduled tasks, Slack, ntfy or Pushover, and
mail or calendar writes, to keep mail local to Apple Mail, to add no tool or service, and to make
the schedule declarative and checked, accepting that `claude` needs a logged-in GUI session, a
one-time macOS Automation approval for Mail and Reminders, and an Artifact tool whose actions
(including delete) cannot be narrowed by a permission rule.

Details that keep the decision testable:

- The launcher (`scripts/secretary/run_morning_briefing.sh`) records the day before it runs, so
  a day starts at most once even after a failure; `--force` overrides it. launchd uses neither
  `RunAtLoad` nor `KeepAlive`; a missed 08:00 runs once after wake.
- The briefing run may write only the two digest state files (through a temporary file and `mv`).
  The launcher itself writes the report under `~/.local/state/secretary/briefings/` and the
  Artifact URL. A second `claude -p` publishes the saved report with separate settings, run outside
  `secretary/` so the read-only settings do not merge with it. If publishing fails, the Markdown
  stays local and the reminder reports the failure.
- Reminder text carries the Artifact URL or a failure notice, never mail contents. The previous
  reminders are completed on the next run.
- Retrieval keeps ADR-0022's primary-source priority and fixed host boundary, but is no longer
  limited to `curl`: `WebFetch` may read primary pages and `WebSearch` may only locate them.
- ADR-0019 (Apple Mail) and ADR-0021 (`gws`) still define the provider clients; only their
  Hermes wording is obsolete. ADR-0010 to ADR-0014 and ADR-0020 were already superseded.
