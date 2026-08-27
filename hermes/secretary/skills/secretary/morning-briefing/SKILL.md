---
name: morning-briefing
description: Summarize today's calendar, mail, research, and technology changes.
version: 0.4.0
author: furedea
license: MIT
platforms: [macos]
metadata:
    hermes:
        tags: [secretary, morning, briefing, research, technology]
        related_skills:
            [calendar-briefing, mail-triage, research-digest, tech-digest]
        blueprint:
            schedule: "0 8 * * *"
            deliver: origin
            prompt: Prepare today's morning briefing using this skill. Keep provider access read-only.
            enabled_toolsets: [web, terminal, skills]
---

# Morning Briefing

Combine the calendar, mail, research, and technology workflows into one concise
report. The blueprint is a versioned routine definition; instantiated cron and
digest state remain local.

## When to Use

- The user manually requests a morning briefing.
- The `morning-briefing` blueprint runs on its configured schedule.

## Procedure

1. Load `calendar-briefing` and summarize today's schedule.
2. Load `mail-triage` and summarize important mail with complete expected-
   account coverage. Do not mutate messages during the briefing.
3. Load `research-digest`. Keep its AI4SE and LLM or agent benchmark tracks
   distinct, and let it update only its local cutoff and disposition state.
4. Load `tech-digest`. Report only its daily P0 and P1 changes, and let it
   update only its local cutoff and disposition state.
5. Produce one concise report in this order:
    - attention now
    - today's schedule
    - mail requiring a decision
    - AI4SE research
    - LLM and agent benchmark research
    - material technology changes
    - coverage gaps

## Pitfalls

- Inferring permission to mutate calendar, mail, Zotero, or dotfiles from a
  scheduled run.
- Hiding a failed account or calendar query behind a partial summary.
- Filling a failed or quiet research source with general news.
- Mixing benchmark research into product and tool release updates.
- Reading cron memory for settings that belong in local Skill config.

## Verification

- All four workflows completed or their failures are named.
- The scheduled run made no provider, Zotero, or dotfiles mutation.
- Only the research and technology local state files may have changed.
- The report was delivered by local Hermes cron state, not written to dotfiles.
