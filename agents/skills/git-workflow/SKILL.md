---
name: git-workflow
description: >
    Use for repository changes and Git delivery: safely organize changes into history and carry
    them through review and integration, including branch/worktree selection, commit boundaries,
    authorized push and PR updates, delivery verification, CI/review conditions, and permitted
    merge and Git cleanup.
---

# Git Workflow

This skill owns safe change history and delivery through review and integration: branch and
worktree selection, commit scope and composition, push and PR creation or updates, delivery
verification and CI/review conditions, and authorized merge and Git cleanup. Receive the Issue
number and plan URL from issue-workflow and associate them with the branch or PR as appropriate.

## Operating Rules

- Inspect Git state before edits: current branch, `git status --porcelain=v1`, and recent commit style when commit messages will be written.
- Never overwrite, reset, clean, or discard user changes unless the user explicitly asked for that exact destructive action.
- Do not push directly to the default / protected branch, and rewrite published history only with the leased force push described in [Delivery](references/delivery.md). Ordinary implementation and PR-creation requests do not authorize merging; merge only when explicitly requested and permitted by repository and runtime rules.
- Complete requested implementation, relevant verification, and fixes for problems caused by the change. Do not stop at the first implementation or first Green when required work remains.
- Commit, push, and create pull requests only within the user's request or an explicit standing authorization. Permission to execute a command is not authorization to perform that action for the task. Do not repeat confirmation for steps already covered by the authorized workflow; runtime approval requirements still apply.
- When commits are authorized, group them by reviewable intent. Multiple TSDD cycles may belong to one commit; do not force a commit for every cycle. Both TSDD paths end Green.
- Keep branch names and commit subjects aligned with the primary intent of the change, not with filenames.

Review-only requests authorize inspection and findings, not edits or delivery. A request to fix a bug
covers implementation and verification, not commits or publication. A request to fix and commit
adds local recording; a request to fix and open a PR also covers necessary commits and pushes, but
not merging.

## Task-Specific References

| Task                                                              | Read                                               |
| ----------------------------------------------------------------- | -------------------------------------------------- |
| Issue creation/reuse, Issue content, and plan comments            | [issue-workflow](../issue-workflow/SKILL.md)       |
| Selecting or changing the checkout, worktree, or branch           | [Branches and worktrees](references/branches.md)   |
| Planning or preparing authorized commits                          | [Commits](references/commits.md)                   |
| Preparing an authorized push, pull request, or rebase             | [Delivery](references/delivery.md)                 |
| Publishing a stacked or red-green pull request the user asked for | [Stacked pull requests](references/stacked_prs.md) |

Read only the reference needed for the current Git operation. Continue to use the selected
checkout and branch while they remain suitable for the task.
