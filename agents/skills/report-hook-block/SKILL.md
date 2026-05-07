---
name: report-hook-block
description: Open a GitHub Issue when a PreToolUse hook actually blocks an action during development and the user wants the block reported. Do not use for designing, editing, testing, or discussing hook allowlists or shell hook files; use bash-style for shell/bats hook work.
allowed-tools: Bash, Read
argument-hint: "<what you were trying to do (optional)>"
---

You are reporting a development blocker caused by a PreToolUse hook. Your goal is to open a GitHub Issue so the hook policy can be reviewed and updated.

The user's description of what they were trying to do: $ARGUMENTS

Read `INSTRUCTIONS.md` (in this skill's directory) for the full procedure before proceeding.
