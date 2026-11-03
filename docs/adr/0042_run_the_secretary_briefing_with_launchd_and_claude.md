# ADR-0042: Run the secretary briefing with launchd and claude -p

- Status: Accepted
- Date: 2026-11-04
- Supersedes: ADR-0022

In the context of the morning briefing losing its Hermes gateway (removed in Issue #378), facing a
resident process, Slack delivery, and a Skill store tied to a Hermes profile, we decided for a
Home Manager `launchd.agents.morning-briefing` that starts `claude -p` once a day at 08:00 from the
`secretary/` directory, with Skills in `secretary/.claude/skills`, a dedicated read-only
`secretary/.claude/settings.json`, state in `~/.local/state/secretary/`, and delivery by the launcher
script, which mails the full plain-text report through Apple Mail from the user's university account
to the same address (read from `~/.local/state/secretary/briefing_address`, never committed), and
against a resident gateway or desktop app, cloud scheduled tasks, Slack, ntfy or Pushover, Apple
Reminders, Artifacts, Claude Docs, and mail or calendar writes by Claude, to keep mail local to
Apple Mail, to add no tool or service, and to make the schedule declarative and checked, accepting
that `claude` needs a logged-in GUI session, a one-time macOS Automation approval for Mail, and that
the self-mail must be kept out of junk filtering by the user.

Why not the alternatives (spike on 2026-11-04): `claude -p` has no Artifact tool, so a fixed Artifact
cannot be published headlessly. Claude Docs and Reminders were dropped to stay with one delivery
path that needs no extra connector, and mail reaches both iPhone and Mac as an ordinary
notification. The recipient is the university account so that university mail content does not leave
it for a personal account.

Details that keep the decision testable:

- The launcher (`scripts/secretary/run_morning_briefing.sh`) records the day before it runs, so
  a day starts at most once even after a failure; `--force` overrides it. launchd uses neither
  `RunAtLoad` nor `KeepAlive`; a missed 08:00 runs once after wake.
- The briefing run may write only the two digest state files (through a temporary file and `mv`).
  The launcher writes the report to `~/.local/state/secretary/briefings/YYYY-MM-DD.md` on every
  successful generation and is the only component that sends mail; Claude's settings deny
  `osascript` and the mail mutation commands.
- The message has the subject `[briefing] YYYY-MM-DD`, is sent from the account that owns the
  address so the provider signs it (no spoofing), and stays in the inbox. On a generation failure
  the launcher mails `[briefing] YYYY-MM-DD 失敗` with the log location. A missing address file or a
  failed send is logged and ends with a non-zero exit code. `mail-triage` excludes `[briefing]`
  self-mail.
- `claude -p` passes `--setting-sources project` with `--settings`, so the broad allow rules of the
  user settings do not merge into the read-only policy. File writes are granted with `Edit(path)`
  rules, which cover the `Write` tool as well.
- Retrieval keeps ADR-0022's primary-source priority and fixed host boundary, but uses the
  read-only `WebFetch` instead of `curl`, because a `curl` allow rule cannot exclude every
  state-changing option (such as `--json`). `WebSearch` may only locate primary sources.
- ADR-0019 (Apple Mail) and ADR-0021 (`gws`) still define the provider clients; only their
  Hermes wording is obsolete. ADR-0010 to ADR-0014 and ADR-0020 were already superseded.
