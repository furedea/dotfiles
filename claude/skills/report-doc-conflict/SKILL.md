---
name: report-doc-conflict
description: Open a GitHub Issue when contradictory instructions in markdown files cause confusion during work
allowed-tools: Bash, Read, Glob
argument-hint: "<description of the conflicting instructions>"
---

You are reporting a development blocker caused by contradictory or inconsistent instructions found in the project's markdown documentation. Your goal is to open a GitHub Issue so the conflict can be resolved.

The user's description of the conflict: $ARGUMENTS

Read `INSTRUCTIONS.md` (in this skill's directory) for the full procedure before proceeding.
