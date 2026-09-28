---
name: github-actions-style
description: >
    Apply this user's conventions when creating, changing, or reviewing GitHub Actions workflows
    and composite actions.
---

# GitHub Actions Coding Conventions

These patterns are easy to overlook but important for security and reliability.

## 1. Permissions — Whitelist Approach

The default `GITHUB_TOKEN` has read/write access to the repo, which is broader than most jobs need. Declare `permissions: {}` at the workflow level (deny-all), then grant only what each job actually requires.

```yaml
permissions: {} # workflow level: deny-all

jobs:
    build:
        permissions:
            contents: read # checkout
            pull-requests: write # post comments
```

Common permission keys: `contents`, `issues`, `pull-requests`, `packages`, `id-token` (OIDC), `checks`, `statuses`.

## 2. Version Pinning

Tags such as `@v4` or `@v4.2.1` can be moved or deleted by the action author, so the same tag may
point to different code over time. Pin every action to a full commit SHA and record the version in
a comment for readability and update tooling.

```yaml
# Avoid — tag can move
- uses: actions/checkout@v4

# Recommended — immutable SHA with the version as a comment
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.1
```

## 3. Script Injection Prevention

GitHub context values like PR titles, issue bodies, and branch names come from untrusted external sources. Interpolating them directly into `run:` allows an attacker to inject arbitrary shell commands. Always pass them through `env:` instead, and quote the variable in the script. This is not escaping: the value never becomes part of the script text.

```yaml
# Dangerous — PR title injected directly into shell
- run: echo "${{ github.event.pull_request.title }}"

# Safe — the shell reads the value from a variable; it is never interpolated into the script
- env:
      TITLE: ${{ github.event.pull_request.title }}
  run: echo "$TITLE"
```

Untrusted inputs include: `github.event.pull_request.title`, `github.event.issue.body`, `github.head_ref`, `github.event.*.name`, any user-controlled field.

## 4. timeout-minutes

The default job timeout is 6 hours. A hung step will consume runner minutes silently. Set an explicit timeout appropriate for the job — typically 5–15 minutes for CI.

```yaml
jobs:
    build:
        timeout-minutes: 10
```

## 5. Shell Settings

Explicitly specifying `shell: bash` causes GitHub Actions to run steps with `bash --noprofile --norc -eo pipefail`, which enables `pipefail` — without it, a failed command in a pipe chain (e.g. `cmd | grep`) can silently succeed.

Set it at the `defaults.run` level to apply to all steps in the workflow or job:

```yaml
defaults:
    run:
        shell: bash
```

For debugging, add `set -x` at the top of a `run:` block to print each command and its output to stderr before execution:

```yaml
- run: |
      set -x
      uv run pytest
```

## 6. Concurrency

When the same workflow can be triggered multiple times simultaneously for the same ref (e.g. rapid commits to a PR branch), earlier runs are typically wasted work. Use `concurrency` to cancel stale runs automatically.

```yaml
# At workflow top-level — cancel previous runs on the same branch/PR
concurrency:
    group: ${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: true # use false for deploy workflows that must run in order
```

This is most useful for `pull_request` and `push` triggers where users push multiple commits in quick succession. Each branch/PR gets its own group, so cancellation is scoped — PR #42 runs do not affect PR #43 runs.

## 7. Cache Design

- Measure representative cold and warm runs before adding a cache. Prefer
  GitHub's cache backend; use an external backend only when self-hosted runner
  locality and measured transfer time justify its credentials and operating
  cost.
- Include every compatibility boundary in the primary key. Use partial matches
  only when the consumer validates and reconciles stale contents; otherwise
  require an exact match. Always keep a correct cache-miss fallback.
- Account for cache scope: pull-request caches are scoped to their merge refs
  and are not reusable by the default branch or sibling pull requests.
- Treat default-branch cache contents as readable by pull requests. Do not
  cache broad paths that may contain credentials. When using an external shared
  backend, do not let untrusted workflows write caches that privileged
  workflows later execute.
