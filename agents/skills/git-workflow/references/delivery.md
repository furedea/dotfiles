# Git Delivery

For implementation tasks:

1. Inspect branch and dirty state.
2. Select the checkout and branch using [Branches and worktrees](branches.md).
3. Follow `tsdd` for development and verification, including path selection and assessing whether refactoring is warranted.
4. Complete the requested change and its relevant verification, fixing problems caused by the change. Report unrelated failures or unavailable verification without claiming success.
5. If delivery is authorized under [Operating Rules](../SKILL.md#operating-rules), commit by intent and perform the requested publication steps:
    - `git fetch origin`
    - optionally `git rebase origin/<base>` before the first push when the feature branch should be refreshed onto the latest base
    - `git push -u origin <branch>`
    - `gh pr create -f --base <base>`
6. Stop before merge; merging is a human decision unless the user explicitly asks for it. When the user asks, `gh pr merge` prompts for approval, and that prompt is the authorization step.

For explicit PR requests:

1. If the user asked for a stacked or red-green pull request, follow [Stacked pull requests](stacked_prs.md) instead of steps 2 and 3.
2. Confirm the target base branch if it is not obvious from the repo default.
3. Push the feature branch with `git push -u origin <branch>`.
4. Create a normal PR with `gh pr create -f --base <base>`.

For rebase and force-push:

- `git rebase origin/<base>` refreshes a PR branch before its first push. Non-interactive rebases onto other refs, including `--onto`, are allowed when the task needs them; reflog can undo them.
- `git rebase --continue` and `git rebase --abort` complete or recover a rebase.
- Interactive rebase is outside the default workflow.
- After rebasing a branch this task already pushed, publish it with `git push --force-with-lease --force-if-includes origin <branch>`. The lease refuses to overwrite commits that were pushed elsewhere, and `--force-if-includes` refuses when a background fetch hid them. Never use bare `--force`, `+refspec` pushes, or any force push to the default branch. If the lease is rejected, stop and ask the user.
