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

Task worktree hand-off through Herdr, once per lane, each line as its own Bash call:

```bash
git fetch origin
herdr workspace list                                         # is the primary checkout already open?
herdr workspace create --cwd <primary-checkout> --label <repo> --no-focus   # only when it is not open
herdr worktree create --workspace <primary-id> --branch <branch> --base origin/<base> --label <branch> --no-focus
herdr agent start <lane-name> --kind claude --pane <root-pane-id> -- --model sonnet --effort medium
herdr agent prompt <lane-name> "Read your brief at <scratchpad>/briefs/<lane-name>.md and carry it out."
herdr agent wait <lane-name> --until working                 # in the background
herdr agent wait <lane-name> --until done --until blocked    # in the background, after the first returns
herdr agent read <lane-name>
```

Rules:

- Run each `herdr` command as a single Bash call. Herdr leaves the sandbox only when the whole
  call is one `herdr` command; chaining (`git fetch origin && herdr ...`) runs it inside the
  sandbox, where it fails. Fetch first in a separate call.
- Keep the prompt text literal. A substitution such as `"$(cat brief.md)"` also makes the call
  more than one `herdr` command. Write the brief to a file in this session's scratchpad and
  prompt the lane to read that file.
- Learn that the lane finished by waiting in the background right after the prompt: first
  `--until working`, then `--until done --until blocked`, each as its own `herdr` call. Waiting
  only for done or blocked can return at once while the agent still shows done from an earlier
  turn. Then read the lane's reply with `herdr agent read` and check its PR. This works for Claude
  and Codex lanes alike.
- With `--cwd` and no open primary workspace, `worktree create` opens one implicitly, which no hook can
  attribute to this session. When `workspace list` shows no workspace for the primary checkout, open
  it yourself with exactly `herdr workspace create --cwd <primary-checkout> --label <repo> --no-focus`
  as one plain call (no `;`, pipe, redirection, wrapper, or extra option), and pass its ID
  (`.result.workspace.workspace_id`) as `--workspace`; `worktree create --workspace` then opens no
  extra workspace. The hooks record a primary this session created from that successful result: ID
  and label from `.result.workspace`, path from `.result.root_pane.cwd` (the result has no checkout
  path), and the root pane's `.result.root_pane.terminal_id`, a per-terminal-instance ID that a
  reused workspace ID or a restarted server never repeats (Herdr exposes no server ID or start
  time). The record lives only in this session's state. A primary that was already open is the
  user's and is never recorded.
- Clean up when the lanes are done, one workspace at a time and never with `--group` (it always asks):
  close each lane (`herdr workspace close <lane-workspace-id>`), then, if this session created the
  primary, `herdr workspace close <primary-id>`. Herdr refuses the primary's close with
  `workspace_group_close_required` while any linked workspace is open. The hooks allow the primary's
  close only while `workspace list` still shows the recorded ID, label, and path
  (`worktree.checkout_path` or the root pane directory), `herdr pane list --workspace <id>` still
  shows the recorded `terminal_id`, and no agent runs in it; otherwise it asks, so accept that one prompt. The record expires on close. The
  session-start sweep below closes only the workspaces of the worktrees it removes, never a primary.
- A variable inside a `gh api` endpoint must be double-quoted (`gh api "repos/o/$r/..."`);
  unquoted expansions ask.
- Read the workspace and root pane IDs from the JSON that `worktree create` returns
  (`.result.workspace.workspace_id`, `.result.root_pane.pane_id`); never predict them.
- `<lane-name>` matches `[a-z][a-z0-9_-]{0,31}` and is new: the hooks let a session prompt only the
  agents it started, and they ask before claiming a name another agent holds.
- Start Claude for an implementation lane, even from a Codex session. Codex keeps a linked
  worktree's Git directory read-only inside its sandbox (openai/codex#14338), so a Codex lane
  cannot commit there without approval. Lanes run on Sonnet at medium effort to save usage; pass
  exactly `-- --model sonnet --effort medium` and nothing else after `--` (a reviewer lane for
  Codex-written code uses `-- --model opus --effort medium`, see
  [herdr-delegation](../../herdr-delegation/SKILL.md)): other agent arguments ask, since they
  could switch off the child's sandbox or approvals.
- The brief follows [herdr-delegation](../../herdr-delegation/SKILL.md) and is self-contained: the
  Issue body and the approved plan text, not only their numbers or links, the lane scope, delivery
  authority (commit, push, and open a PR; never merge), and the reply format.
- A linked worktree session cannot write another repository's `.git`, and this session cannot
  fetch another repository for it, so the lane fetches and rebases onto its base before editing.
- Herdr places the checkout under its `worktrees.directory`; do not pass `--path` without a reason.
- Merged task worktrees and branches, in this repository and every repository with a Herdr task
  worktree, are removed at the next Claude session start, or on demand
  with `~/.claude/hooks/cleanup_worktrees.py [--dry-run]`: only when a merged pull request's head
  is the branch tip and the tree is clean, and the primary checkout's `main` then fast-forwards.
  Do not delete them or pull by hand. An abandoned worktree is
  the user's to remove. Moving and repairing worktrees stay outside the agent workflow.
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
