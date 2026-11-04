---
name: morning-briefing
description: Summarize today's calendar, mail, research, and technology changes.
---

# Morning Briefing

Combine calendar, mail, research, and technology workflows into one concise
report. The report is the final assistant message; the launcher script that runs
this Skill owns saving and delivering it.

## When to Use

- The user manually requests a morning briefing.
- The `morning-briefing` launchd agent runs `claude -p` from `secretary/`.

## Procedure

1. Load `calendar-briefing` and summarize today's schedule from the exported
   calendar JSON.
2. Load `mail-triage` and summarize important mail with complete expected-
   account coverage. Do not mutate messages during the briefing.
3. Load `ai-research-digest`. Keep its AI4SE and LLM or agent benchmark sections
   separate. It may update only its local digest state.
4. Load `toolchain-digest`. Report only daily P0 and P1 changes. It may update only
   its local digest state.
5. Produce one concise Japanese report. Its first line is exactly
   `coverage: complete` when the calendar JSON had `ok` true and every other
   workflow covered all its sources, otherwise exactly `coverage: partial`. The
   launcher reads and strips that line to set the mail subject. Then write, in
   this order:
    - attention now
    - today's schedule
    - mail requiring a decision
    - AI4SE research
    - LLM and agent benchmark research
    - material technology changes
    - coverage gaps

## Authority Policy

Provider access remains read-only. A scheduled run cannot change calendar,
mail, dotfiles, dependencies, packages, or external accounts. The only allowed
writes are the two local digest state files defined by the related
Skills.

## Pitfalls

- Inferring permission to mutate a provider or dotfiles from a scheduled run.
- Hiding a failed account, calendar, or source query behind a partial summary.
- Filling a failed or quiet research source with general news.
- Mixing benchmark research into product and tool release updates.
- Writing or sending the report yourself; the launcher saves it and mails it.

## Verification

- All four related workflows completed or their failures are named.
- Calendar and mail provider access remained read-only.
- Only the two local digest state files may have changed.
- The report is the final message and was not written to dotfiles.
