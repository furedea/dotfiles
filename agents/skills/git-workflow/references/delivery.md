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
6. Stop before merge; merging is a human decision unless the user explicitly asks for it.

For explicit PR requests:

1. Confirm the target base branch if it is not obvious from the repo default.
2. Push the feature branch with `git push -u origin <branch>`.
3. Create a normal PR with `gh pr create -f --base <base>`.

For rebase and force-push:

- `git rebase origin/<base>` is allowed before the first push for a PR branch.
- `git rebase --continue` and `git rebase --abort` are allowed to complete or recover from that narrow workflow.
- Interactive rebase, `--onto`, and rebasing onto local branches are outside the default workflow; ask before using them.
- `git push --force`, `git push --force-with-lease`, and `+refspec` pushes are not part of the default workflow. Stop and ask the user if a remote history rewrite is genuinely required.
