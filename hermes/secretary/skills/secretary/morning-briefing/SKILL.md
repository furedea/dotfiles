---
name: morning-briefing
description: Combine calendar, mail, and X into a morning briefing.
version: 0.2.0
author: furedea
license: MIT
platforms: [macos]
metadata:
    hermes:
        tags: [secretary, morning, briefing]
        related_skills: [calendar-briefing, mail-triage, x-morning-digest]
        blueprint:
            schedule: "0 8 * * *"
            deliver: origin
            prompt: Prepare today's morning briefing using this skill. Keep the run read-only.
            enabled_toolsets: [terminal, skills]
---

# Morning Briefing

Combine the three secretary workflows into one concise report. The blueprint
is a versioned routine definition; instantiated cron state remains local.

## When to Use

- The user manually requests a morning briefing.
- The `morning-briefing` blueprint runs on its configured schedule.

## Procedure

1. Load `calendar-briefing` and summarize today's schedule.
2. Load `mail-triage` and summarize important mail with complete expected-
   account coverage. Do not mutate messages during the briefing.
3. Load `x-morning-digest` and summarize material posts from local Skill
   configuration.
4. Produce one concise report in this order:
    - attention now
    - today's schedule
    - mail requiring a decision
    - X highlights
    - coverage gaps

## Pitfalls

- Inferring permission to mutate calendar or mail from a scheduled run.
- Hiding a failed account, calendar query, or X query behind a partial summary.
- Reading cron memory for settings that belong in local Skill config.

## Verification

- All three related skills completed or their failures are named.
- The scheduled run made no calendar, mail, or X mutation.
- The report was delivered by local Hermes cron state, not written to dotfiles.
