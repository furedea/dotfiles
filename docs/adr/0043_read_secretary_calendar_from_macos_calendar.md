# ADR-0043: Read the secretary calendar from macOS Calendar

- Status: Superseded
- Date: 2026-11-04
- Supersedes: ADR-0021
- Superseded by: ADR-0044

In the context of the morning briefing needing today's events after the first launchd run
(ADR-0042) returned `gws` 401 because its credentials were lost with `~/.hermes`, facing a
self-made Google OAuth app (GCP project, consent screen, publishing status, re-login every seven
days) for data that Calendar on the Mac already holds, we decided for exporting today's events from
macOS Calendar with `osascript -l JavaScript` and EventKit in the launcher script, and for having
`claude -p` only read the resulting JSON, and against `gws`, `gogcli`, a custom Calendar API
client, and AppleScript's Calendar dictionary (it does not expand recurring events), to need no
Google Cloud setup or periodic login, to include recurring and subscribed calendars, and to keep
Claude unable to write to the calendar, accepting a one-time macOS approval of full Calendar
access and that the Google calendar must already sync to Calendar on this Mac.

Details that keep the decision testable:

- The launcher writes `~/.local/state/secretary/calendar/YYYY-MM-DD.json` for 00:00 to 24:00
  local time with the calendar name, title, start, end, all-day flag, and location of every event
  in every calendar. A failure (no permission, timeout, invalid output) is written as
  `{"ok":false,"error":...}` and the briefing continues; the report lists it as a coverage gap.
- Claude's settings keep denying `osascript`; only the launcher runs it. The `google-calendar`
  Skill is removed and `calendar-briefing` reads the JSON.
- The report's first line is `coverage: complete` or `coverage: partial`. The launcher strips it
  from the mail body and uses `[briefing] YYYY-MM-DD（一部取得失敗）` as the subject when the line
  is not `complete` (a missing line counts as partial) or the calendar JSON is not `ok`.
- Mail is launched before sending and every Mail command runs inside `with timeout of 300 seconds`.
  The AppleScript no longer loops over accounts reading `email addresses` (it timed out with -1712 in
  the second real run); it sets the sender to the address directly and reports the failing step. A
  failed send is retried once. `--resend` mails the saved report of the day without generating it.
- `gws`, `~/.config/gws`, `calendar_id`, the GCP project, and the contents of ADR-0013 and
  ADR-0021 stay until the new path is confirmed to deliver; their removal is a separate Issue.
