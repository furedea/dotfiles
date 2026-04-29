---
name: git-commit-split
description: >
    Split pending git changes (modified, untracked, and already-staged) into multiple feature-grained commits with Conventional Commits messages, optionally pairing each commit with its own branch and draft PR. Use whenever the user asks to "commit", "コミットして", "make commits", "split into commits", "1 機能 1commit", "1 コミット 1 機能", "commit unstaged files", "未ステージを commit", "branch 切って PR", "PR 分けて", "1 機能 1PR", "stack PR", "draft PR", "ドラフト PR", or any phrasing that implies organizing pending git changes into well-structured commits. Supports two modes: `direct` (commit on the current branch) and `pr-per-feature` (one branch + one draft PR per commit, independent or stacked). The user must set the mode explicitly; never auto-detect it. Present commit grouping and branch/PR strategy as one plan for approval before any branch or commit lands. Prevent vague "update files" commits, direct pushes to protected main, and missing Conventional Commits formatting.
---

Read `INSTRUCTIONS.md` first; it owns Phase 0-2 (mode / inspect / plan) and the Phase 3 router. The other files here are **read on demand**, not all at once — that's how the skill keeps the working context tight even though it covers multiple modes.

## Navigation map (read-on-demand)

- Always start with: `INSTRUCTIONS.md`
- Phase 2 (plan) — Conventional Commits type/scope/subject style: `references/conventional_commits.md`
- Phase 3 (execute), `direct` mode: `references/direct_execute.md`
- Phase 3 (execute), `pr-per-feature` mode (independent or stack): `references/pr_per_feature_execute.md`
- Hunk-level partial apply (any mode, when one file's hunks split across commits): `references/hunk_split.md`
- Generate a kebab-case branch slug from a commit subject (with collision avoidance): `scripts/branch_name.py`
- Filter a unified diff to a subset of hunks: `scripts/build_partial_patch.py`
