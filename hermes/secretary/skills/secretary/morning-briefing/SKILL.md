---
name: morning-briefing
description: Combine calendar, multi-account mail, and X into one concise morning briefing.
version: 0.1.0
author: furedea
license: MIT
platforms: [macos]
metadata:
    hermes:
        tags: [secretary, morning, briefing]
        related_skills: [calendar-briefing, mail-triage, x-morning-digest]
---

# Morning Briefing

Use this skill for the scheduled or manually requested morning briefing.

## Procedure

1. Load `calendar-briefing` and summarize today's schedule.
2. Load `mail-triage` and summarize important mail across every configured
   account without mutating messages.
3. Load `x-morning-digest` and summarize material new posts from the local
   watchlist.
4. Present one concise report in this order:
    - attention now
    - today's schedule
    - mail requiring a decision
    - X highlights
    - coverage gaps
5. Do not persist the report in managed files. Delivery is owned by the local
   Hermes gateway and cron job configuration.

## Safety

- The scheduled run is read-only.
- Do not infer permission to change calendar or mail from a routine run.
- Do not add a delivery target or schedule until the user specifies it.
