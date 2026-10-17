# Branches and Worktrees

Implementation starts only after the user approves the plan (see
[issue-workflow](../../issue-workflow/SKILL.md)). Each lane of the approved plan then runs in its own
task worktree and session, so lanes never share a checkout and the user's checkout stays untouched.

Choose the workspace in this order:

1. If this session already runs in a task worktree on a non-default branch for this task, stay there.
2. If the user explicitly asks to stay in the current checkout, create the task branch there with
   `git switch -c <branch>`, unless that would overwrite or mix unrelated changes.
3. If Herdr is available (`HERDR_ENV=1`), hand each lane to a new task worktree session as below.
4. Without Herdr, create the task branch in the current checkout for a single lane when the tree is
   clean or its changes belong to this task. For several lanes, or unrelated dirty changes, report
   that each lane needs its own worktree session and stop: a sandboxed session cannot write a
   sibling checkout.
5. If the target branch is already checked out in another worktree, use that worktree or choose a
   different branch name. Do not force-checkout the same branch in two places.

Task worktree hand-off through Herdr, once per lane:

```bash
git fetch origin
herdr worktree create --cwd <primary-checkout> --branch <branch> --base origin/<base> --label <branch> --no-focus
herdr agent start <lane-name> --kind <claude|codex> --pane <root-pane-id>
herdr agent prompt <lane-name> "<brief>"
```

Rules:

- Read the workspace and root pane IDs from the JSON that `worktree create` returns
  (`.result.workspace.workspace_id`, `.result.root_pane.pane_id`); never predict them.
- `<lane-name>` matches `[a-z][a-z0-9_-]{0,31}` and is new: the hooks let a session prompt only the
  agents it started, and they ask before claiming a name another agent holds.
- Start the same provider as this session unless the user chose another. Pass nothing after `--`:
  agent arguments are denied, since they could switch off the child's sandbox or approvals.
- The brief follows [herdr-delegation](../../herdr-delegation/SKILL.md): Issue, plan link, lane scope,
  and delivery authority (commit, push, and open a PR; never merge).
- Herdr places the checkout under its `worktrees.directory`; do not pass `--path` without a reason.
- Remove a task worktree only after its branch is merged or abandoned and its tree is clean; never
  force removal. Use `herdr worktree remove --workspace <id>`, which runs `git worktree remove`
  and keeps the branch. Moving and repairing worktrees stay outside the agent workflow.
- When updating `main` itself, use `git pull --ff-only` in the main worktree. Do not use
  `git pull --rebase origin main` for the base branch.
- For a requested stacked pull request, `gh stack init` and `gh stack add` create the layer branches;
  the branch name format below applies to each layer. See [Stacked pull requests](stacked_prs.md).

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
