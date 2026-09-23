# Git Delivery

For implementation tasks:

1. Inspect branch and dirty state.
2. Select the checkout and branch using [Branches and worktrees](branches.md).
3. Follow `tsdd` for development and verification, including path selection and assessing whether refactoring is warranted.
4. Complete the requested change and [Local Verification Before Delivery](#local-verification-before-delivery), fixing problems caused by the change. Report unrelated failures or unavailable verification without claiming success.
5. If delivery is authorized under [Operating Rules](../SKILL.md#operating-rules), commit by intent and perform the requested publication steps:
    - `git fetch origin`
    - optionally `git rebase origin/<base>` before the first push when the feature branch should be refreshed onto the latest base
    - `git push -u origin <branch>`
    - `gh pr create --base <base> --title "<title>" --body-file <file>`, with a [pull request body](#pull-request-body)
6. Stop before merge; merging is a human decision unless the user explicitly asks for it. When the user asks, `gh pr merge` prompts for approval, and that prompt is the authorization step.

For explicit PR requests:

1. If the user asked for a stacked or red-green pull request, follow [Stacked pull requests](stacked_prs.md) instead of steps 2 and 3.
2. Confirm the target base branch if it is not obvious from the repo default.
3. Follow [Local Verification Before Delivery](#local-verification-before-delivery), then push the feature branch with `git push -u origin <branch>`.
4. Create a normal PR with `gh pr create --base <base> --title "<title>" --body-file <file>`, with a
   [pull request body](#pull-request-body).

For rebase and force-push:

- `git rebase origin/<base>` refreshes a PR branch before its first push. Non-interactive rebases onto other refs, including `--onto`, are allowed when the task needs them; reflog can undo them.
- `git rebase --continue` and `git rebase --abort` complete or recover a rebase.
- Interactive rebase is outside the default workflow.
- After rebasing a branch this task already pushed, publish it with `git push --force-with-lease --force-if-includes origin <branch>`. The lease refuses to overwrite commits that were pushed elsewhere, and `--force-if-includes` refuses when a background fetch hid them. Never use bare `--force`, `+refspec` pushes, or any force push to the default branch. If the lease is rejected, stop and ask the user.

## Pull Request Body

Write the title as a Conventional Commits subject stating the primary intent, and keep the body
short. Do not use `-f`/`--fill`; commit messages do not carry this content. The body must include:

- A few lines on what actually changed.
- `Closes #N` only when the PR fully resolves the Issue; otherwise `Refs #N`.
- A link to the plan comment, when one exists.
- Verification evidence: what ran and its result, or what could not run.
- Material departures from the plan, or none.

For what the PR body owns relative to the Issue and plan, follow
[Information Placement](../../source-of-truth/SKILL.md#information-placement).

## Local Verification Before Delivery

1. Complete required local verification before delivery without waiting for Stop.
2. Normally invoke the shared verify entry point while preparing the delivery commit.
3. Let shared verify reuse valid results when available.
4. Let the existing pre-commit hooks run normally at commit time.
5. Refresh necessary evidence if formatting, fixes, rebase, or other changes alter inputs after
   verification.
6. After PR creation, check CI and review requirements and proceed only to the authorized stage.

Stop does not necessarily run before commit, push, or merge, so it cannot be the only delivery
gate. For conditions requiring manual checks, follow
[TSDD Automatic Verification](../../tsdd/SKILL.md#automatic-verification).

## Verification Commands

Use the current record registered and reported by SessionStart as `<session-record>`. Never select
a record merely because its modification time is newest.

```bash
"$HOME/.claude/hooks/verification_session.py" verify "<session-record>"
```

Normally call verify directly before delivery; a status-then-verify sequence is not required.
When freshness is unclear, inspect state without starting checks:

```bash
"$HOME/.claude/hooks/verification_session.py" status "<session-record>"
```

Status exit code 0 means the query succeeded, not that verification passed. Judge verification
from the returned state and each result's applicability.
