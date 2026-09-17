---
name: herdr-delegation
description: >
    Use when the user requests a plan review, code review, or implementation task in a separate
    Codex or Claude session through Herdr, including another repository or worktree. Applies
    when Herdr is requested or already selected for the delegation, not to ordinary local work.
---

# Herdr Delegation

Delegate a bounded task to an independent coding-agent session. The originating session owns
the request, evaluates the returned work, and reports the outcome to the user.

## Scope and Dependencies

- Apply this workflow to requested cross-session work. Do not infer permission to delegate from
  an ordinary coding request, a local review, or an opportunity to work in parallel.
- Read the `herdr` skill before operating another session. It owns prerequisites, CLI discovery,
  agent identity, layout, prompting, waiting, approvals, and recovering complete output. Follow
  its environment check; if Herdr is unavailable, report the limitation without silently
  switching to another transport.
- Use `git-workflow` for branch and worktree choices and authorized Git delivery. Delegation
  alone does not require a new worktree or authorize commits, pushes, or pull requests.
- Use `tsdd` and the target repository's applicable conventions for implementation and
  verification. Each session must follow its own repository instructions and permission rules.

## Choose the Task and Recipient

| Request                                    | Default recipient                                                  | Authority                                              |
| ------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------ |
| Review a plan                              | Claude for a Codex-authored plan; Codex for a Claude-authored plan | Findings only; do not rewrite the plan or implement it |
| Review code                                | Claude for Codex-authored code; Codex for Claude-authored code     | Findings only; do not edit the reviewed source         |
| Implement in another directory or worktree | A separate Codex session in the requested location                 | Changes limited to the delegated scope                 |

Honor an explicit provider choice. Keep plan review, code review, and implementation as distinct
assignments; asking for findings does not authorize the reviewer to fix them.

Reuse an existing session only when its identity, location, and current assignment make it the
intended recipient. Otherwise create a separate session through `herdr`. Use the requested
repository or worktree; do not substitute another checkout just because its directory name matches.
Allow only one implementation writer per checkout at a time.

## Prepare a Self-Contained Brief

The recipient does not inherit the originating conversation. Supply:

- **Task:** plan review, code review, or implementation, with the requested outcome.
- **Requirements:** the user's relevant requirements, accepted decisions, constraints, and links
  to authoritative repository material. Distinguish requirements from the author's assumptions.
- **Location:** the absolute repository or worktree path, branch, and relevant base and head
  commits. Tell the recipient to read the applicable instructions in that location.
- **Input:** the exact plan text or plan file, code review range, or implementation scope. For
  uncommitted code, identify whether staged, unstaged, and untracked files are included.
- **Authority:** permitted edits, excluded files or tasks, and any existing delivery authorization.
- **Completion:** observable acceptance conditions, relevant verification, and the expected
  response described below.

Resolve discoverable context before asking the user. Ask only when a missing requirement,
location, or permission prevents a correct assignment. Reuse authorization already given.

Keep the reviewed input stable until the review completes. For uncommitted work, pause writes
to that checkout or use an explicitly selected isolated snapshot containing all reviewed files.
A result for an earlier plan or revision is not evidence that later changes were reviewed.

## Review Assignments

For a **plan review**, ask the reviewer to compare the proposal independently with the
requirements and relevant repository facts. Look for missing requirements, unsupported
assumptions, incorrect boundaries, migration gaps, and verification that would not distinguish
success from failure. Request findings and necessary corrections, not a replacement plan.

For a **code review**, ask the reviewer to inspect the specified changes in their surrounding
context. Prioritize actionable bugs, regressions, contract violations, and missing evidence for
required behavior. Relevant checks may be run within the session's permissions; source changes
remain outside a review assignment.

Request findings ordered by severity. Each finding should identify the affected plan section or
file and line, the violated requirement or concrete failure scenario, its impact, and supporting
evidence. Separate unresolved hypotheses from confirmed findings. If none are found, say so
explicitly and state the reviewed scope and any verification limits.

## Implementation Assignments

Have the worker confirm the actual repository root, branch, and dirty state before editing.
Preserve pre-existing changes and resolve conflicting ownership before starting work. Keep
implementation inside the assigned scope; report dependencies on another repository or a
broader change instead of silently expanding the assignment.

Ask the worker to return:

- What changed and how it satisfies the requested outcome.
- Changed files, working directory, and branch; commit IDs when committing was authorized.
- Checks performed and their results, including failures or checks that could not run.
- Remaining work, unresolved decisions, and any blocker that prevents completion.

## Run and Reconcile

Submit the brief through `herdr` and retain the recipient identity and input revision in the
originating session. Follow `herdr` for waiting, blocked sessions, and complete response retrieval.
Successful submission or a settled agent state does not prove that the assigned task is complete;
read the response and compare it with the requested outcome.

Evaluate review findings against the requirements and evidence before changing the work.
Apply accepted corrections within the user's scope and seek a focused follow-up review when
material changes leave the earlier review incomplete. Resolve disputed findings with evidence;
do not manufacture consensus by repeating the same review request.

For implementation, inspect the actual diff and verification evidence in the assigned repository
before reporting success. When requested completion includes integrating another worktree's
changes, follow `git-workflow` for authorized integration and report anything still pending.
Do not infer that changes reached the intended branch merely because the worker finished.

Report the provider and reviewed or changed scope, the resulting findings or implementation,
verification evidence, and unresolved limitations. Keep the final response with the originating
session; a worker's completion message does not replace this reconciliation.
