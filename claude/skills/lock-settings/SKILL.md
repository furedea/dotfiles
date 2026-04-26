---
name: lock-settings
description: Add deny rules to protect settings and hook files from Claude Code modification. Run after a feature PR that adds/modifies settings or hooks has been merged.
allowed-tools: []
---

Add deny rules (Edit and Write) and sandbox `denyWrite` entries for settings and hook files that should be locked from Claude Code modification.

Read `INSTRUCTIONS.md` (in this skill's directory) for the full procedure before proceeding.
