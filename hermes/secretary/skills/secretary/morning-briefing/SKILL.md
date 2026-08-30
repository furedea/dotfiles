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
            prompt: Prepare today's briefing. Keep providers read-only; only local digest state may change.
            enabled_toolsets: [terminal, skills]
---

# Morning Briefing

Combine calendar, mail, research, and technology workflows into one concise
report. The blueprint is a versioned routine definition; instantiated cron and
digest state remain local.

## When to Use

- The user manually requests a morning briefing.
- The `morning-briefing` blueprint runs on its configured schedule.

## Procedure

1. Load `calendar-briefing` and summarize today's schedule.
2. Load `mail-triage` and summarize important mail with complete expected-
   account coverage. Do not mutate messages during the briefing.
3. Load `research-digest`. Keep its AI4SE and LLM or agent benchmark sections
   separate. It may update only its local digest state.
4. Load `tech-digest`. Report only daily P0 and P1 changes. It may update only
   its local digest state.
5. Produce one concise report in this order:
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
writes are the two profile-local digest state files defined by the related
Skills.

## Pitfalls

- Inferring permission to mutate a provider or dotfiles from a scheduled run.
- Hiding a failed account, calendar, or source query behind a partial summary.
- Filling a failed or quiet research source with general news.
- Mixing benchmark research into product and tool release updates.
- Reading cron memory for settings owned by a Skill.

## Verification

- All four related workflows completed or their failures are named.
- Calendar and mail provider access remained read-only.
- Only the two local digest state files may have changed.
- The report was delivered by local Hermes cron state, not written to dotfiles.
