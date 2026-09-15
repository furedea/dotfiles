---
name: git-workflow
description: >
    Git workflow for selecting a branch before edits and carrying out authorized commits, pushes,
    and pull requests, including organizing mixed pending changes. Use for repository changes
    or Git delivery tasks.
---

# Git Workflow

This skill governs the default Git shape of implementation work: which branch to use, how to name it, how to cut commits, and when it is safe to push or open a PR.

## Operating Rules

- Inspect Git state before edits: current branch, `git status --porcelain=v1`, and recent commit style when commit messages will be written.
- Never overwrite, reset, clean, or discard user changes unless the user explicitly asked for that exact destructive action.
- Do not force-push or push directly to the default / protected branch. Ordinary implementation and PR-creation requests do not authorize merging; merge only when explicitly requested and permitted by repository and runtime rules.
- Complete requested implementation, relevant verification, and fixes for problems caused by the change. Do not stop at the first implementation or first Green when required work remains.
- Commit, push, and create pull requests only within the user's request or an explicit standing authorization. Permission to execute a command is not authorization to perform that action for the task. Do not repeat confirmation for steps already covered by the authorized workflow; runtime approval requirements still apply.
- When commits are authorized, group them by reviewable intent. Multiple TSDD cycles may belong to one commit; do not force a commit for every cycle. Both TSDD paths end Green.
- Keep branch names and commit subjects aligned with the primary intent of the change, not with filenames.

Review-only requests authorize inspection and findings, not edits or delivery. A request to fix a bug
covers implementation and verification, not commits or publication. A request to fix and commit
adds local recording; a request to fix and open a PR also covers necessary commits and pushes, but
not merging.

## Task-Specific References

| Task                                                    | Read                                             |
| ------------------------------------------------------- | ------------------------------------------------ |
| Selecting or changing the checkout, worktree, or branch | [Branches and worktrees](references/branches.md) |
| Planning or preparing authorized commits                | [Commits](references/commits.md)                 |
| Preparing an authorized push, pull request, or rebase   | [Delivery](references/delivery.md)               |

Read only the reference needed for the current Git operation. Continue to use the selected
checkout and branch while they remain suitable for the task.
