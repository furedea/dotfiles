---
name: report-hook-block
description: Open a GitHub Issue when a PreToolUse hook blocks an action during development
allowed-tools: Bash, Read
argument-hint: "<what you were trying to do (optional)>"
---

You are reporting a development blocker caused by a PreToolUse hook. Your goal is to open a GitHub Issue so the hook policy can be reviewed and updated.

The user's description of what they were trying to do: $ARGUMENTS

Read `INSTRUCTIONS.md` (in this skill's directory) for the full procedure before proceeding.
