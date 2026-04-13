---
name: github-ci-init
description: >
    GitHub Actions CI scaffolding for this user. Installs the curated "default adopted set" — actionlint + zizmor workflow hygiene, dependency review, CodeQL, release-please — by copying bundled workflow templates into a repository's `.github/`. Load whenever the user wants to add CI, GitHub Actions, automated quality checks, CodeQL, Dependabot-style dependency monitoring, release-please, or retrofit CI onto an existing repository. This skill is DISTINCT from `gha-style` (which covers the coding conventions for writing and editing individual workflow files) — load THIS one for the initial scaffolding (the "which workflows ship and where do they go" decision), then hand off to `gha-style` for any per-file editing afterwards. Also trigger on "/github-ci-init", "set up CI", "add GitHub Actions", "add CodeQL", "release-please", "dependency review", "actionlint", "zizmor", ".github/workflows/", or any mention of project-level CI bootstrap.
---

Read `INSTRUCTIONS.md` (in this skill's directory) for the judgment criteria, copy procedure, and handoff rules before proceeding.
