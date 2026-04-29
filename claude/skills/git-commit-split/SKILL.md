---
name: git-commit-split
description: >
    Split pending git changes (modified, untracked, and already-staged) into multiple feature-grained commits with Conventional Commits messages, optionally pairing each commit with its own branch and draft PR. Use this skill whenever the user asks to "commit", "コミットして", "make commits", "split into commits", "1 機能 1commit", "1 コミット 1 機能", "commit unstaged files", "未ステージを commit", "branch 切って PR", "PR 分けて", "1 機能 1PR", "stack PR", "draft PR", "ドラフト PR", or any phrasing that implies organizing pending git changes into well-structured commits — even when they don't explicitly say "split". The skill supports two delivery modes: `direct` (commit on the current branch) and `pr-per-feature` (one branch + one draft PR per commit, either independent off the base branch or stacked); the mode is always set explicitly by the user — never auto-detected — and both the commit grouping AND the branching/PR strategy are presented as a single plan for approval before any branch or commit lands. Without this skill, Claude tends to lump everything into a single vague "update files" commit, push directly to a protected main, or skip Conventional Commits formatting.
---

Read `INSTRUCTIONS.md` (in this skill's directory) for the full reference before proceeding.
