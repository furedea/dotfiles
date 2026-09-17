---
name: issue-workflow
description: >
    Use to secure an Issue needed for ordinary implementation, explicitly create or update
    Issues, save or update implementation plans in Issue comments, or resume and reconcile
    Issue-based work. Explanation, investigation, review, or plan discussion alone does not
    authorize publication or implementation.
---

# Issue Workflow

## Scope

Own Issue creation, reuse, and updates; managed plan comments; links among the Issue, plan,
and related PRs; identification of existing information on resume; and Issue and plan status.
Follow the existing user-managed authorization policy and the current request. This skill does
not define standing permissions or expand publication authority.

Delegate other responsibilities:

- Branches, worktrees, commits, pushes, PR creation, and merges → [git-workflow](../git-workflow/SKILL.md).
- Testing and implementation methodology → [tsdd](../tsdd/SKILL.md).
- Information authority and temporary document lifetime → [source-of-truth](../source-of-truth/SKILL.md).
- Design decision records → [adr](../adr/SKILL.md).

## Issue Resolution

1. Confirm the destination repository and the purpose of this task.
2. Prefer a user-specified Issue or one already associated with the current work.
3. Search relevant existing Issues only when the appropriate Issue is unclear.
4. If none fits, create an Issue in an authorized destination.
5. Confirm the number and URL of the created or retrieved Issue.

Include purpose, scope, necessary exclusions, acceptance criteria, and related sources in the
Issue body. Do not turn assumptions into established requirements. Reuse the same Issue for
continuation, PR revisions, and individual commits within one task.

If a posting result is uncertain, check whether creation succeeded before retrying. Never post
the conversation verbatim or include secrets.

## Plan Comments

- Reuse a supplied implementation plan and save the necessary portion in an Issue comment.
- Create and share a short plan when the work needs multiple stages, significant design
  decisions, migration, or handoff across sessions. Omit a plan for an obvious, short fix.
- A request only to discuss a plan does not authorize publication or implementation.
- Include major steps, verification strategy, and important assumptions or unresolved questions.
- Confirm the posted comment ID or permalink; do not post the same plan twice.
- Update the managed comment for significant changes in direction rather than adding comments
  for routine progress. Read its current contents first and preserve user additions.
- Identify the managed comment by its recorded identity, never merely because it is the latest.
- A local plan file and commits recording that file are optional, not prerequisites.

For plan authority, completion handling, and temporary-file deletion, follow
[Information Placement](../source-of-truth/SKILL.md#information-placement) and
[Temporary Implementation Briefs](../source-of-truth/SKILL.md#temporary-implementation-briefs).

## Resume and Completion

- Identify and reuse this task's Issue, relevant plan, and related PRs when resuming. Do not load
  all past Issues or plan comments.
- Distinguish implementation complete, PR created, merge complete, and Issue complete.
- Leave merge operations to git-workflow and confirm their result here.
- Only when the entire Issue is resolved, check whether it is closed. Do not close an Issue with
  partial implementation or unresolved work.
- When needed, reflect completion status and related PRs in the managed plan comment.
- Clean temporary local notes according to source-of-truth's deletion conditions.
