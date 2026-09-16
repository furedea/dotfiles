# Branches and Worktrees

Prefer a feature branch in the current checkout for a single active task. Create a separate worktree only in the cases listed below.

Choose the workspace in this order:

1. If the user explicitly asks for a worktree, parallel work, isolated work, or another simultaneous task, create a sibling worktree.
2. If the user explicitly asks to avoid worktrees or continue in the current checkout, stay in the current checkout unless doing so would overwrite or mix unrelated changes.
3. If already on a suitable non-default branch for the task, stay there.
4. If on `main`, `master`, a release branch, or another protected/default branch:
    - If the working tree is clean, create the task branch in the current checkout with `git switch -c <branch>`.
    - If dirty changes clearly belong to this task, create the task branch in the current checkout and keep those changes.
    - If dirty changes are unrelated to this task, create a sibling worktree.
    - If ownership of dirty changes is unclear, ask before switching branches or creating a worktree.
5. If on a non-default branch for a different task:
    - If the new request is a continuation of that branch, stay there.
    - If the new request is unrelated, create a sibling worktree.
6. If the target branch is already checked out in another worktree, use that worktree or choose a different branch name. Do not force-checkout the same branch in two places.

Current-checkout branch creation:

```bash
git switch -c <branch>
```

Task worktree creation:

```bash
git pull --ff-only  # when on the main worktree and updating the base branch
git fetch origin
git worktree add -b <branch> ../<repo-name>-<branch-path-slug> origin/<base>
cd ../<repo-name>-<branch-path-slug>
```

Rules:

- `<branch>` follows the branch name format below.
- `<branch-path-slug>` is the branch name with `/` replaced by `-`.
- Put task worktrees as siblings of the primary checkout under the same parent directory.
- Example: primary checkout `/Users/kaito/ghq/github.com/furedea/agent-harness` with branch `ci/codex-conformance` uses `/Users/kaito/ghq/github.com/furedea/agent-harness-ci-codex-conformance`.
- Append `-2`, `-3`, etc. to the worktree path if it already exists.
- When updating `main` itself, use `git pull --ff-only` in the main worktree. Do not use `git pull --rebase origin main` for the base branch.
- Do not remove, prune, move, or repair worktrees from the agent workflow; report stale worktrees to the user instead.

Branch name format:

```text
<type>/<kebab-subject>
```

Rules:

- `<type>` is the Conventional Commits type that would be used for the primary commit: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`, `style`, or `revert`.
- `<kebab-subject>` is lowercase ASCII, hyphen-separated, derived from the imperative commit subject with no scope.
- Omit Conventional Commits scope from branch names.
- Append `-2`, `-3`, etc. if a local or remote branch already exists.

Examples:

```text
feat/jwt-refresh-token-rotation
fix/parser-empty-input
refactor/extract-query-builder
docs/clarify-install-steps
```
