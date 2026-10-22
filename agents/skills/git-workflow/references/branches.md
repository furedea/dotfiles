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
- A variable inside a `gh api` endpoint must be double-quoted (`gh api "repos/o/$r/..."`);
  unquoted expansions ask.
- Keep the prompt text literal. A substitution such as `"$(cat brief.md)"` also makes the call
  more than one `herdr` command. Write the brief to a file in this session's scratchpad and
  prompt the lane to read that file.
- Learn that the lane finished by waiting in the background right after the prompt: first
  `--until working`, then `--until done --until blocked`, each as its own `herdr` call. Waiting
  only for done or blocked can return at once while the agent still shows done from an earlier
  turn. Then read the lane's reply with `herdr agent read`, check for `LANE-READY`, check the PR
  state, and report to the user. Treat `LANE-BLOCKED` and its reason as incomplete work. This
  works for Claude and Codex lanes alike.
- The lane runs the whole loop: asks Codex to implement, verifies, commits, pushes, opens the PR,
  then starts the reviewer itself. For Codex's implementation, use an Opus subagent with only
  the requirements and the diff; for Claude's, use the Codex review command. The lane has Codex
  fix accepted findings and waits for CI. It ends its final message with `LANE-READY` only when
  CI is green and no review finding is open; otherwise it ends with `LANE-BLOCKED` and the reason.
- The lane never types into the parent's pane with `herdr agent prompt` or `send-text`: text
  typed there is indistinguishable from the user's own input.
- Open the primary checkout's workspace yourself when `workspace list` shows none, and pass its
  `.result.workspace.workspace_id` to `worktree create --workspace`; with `--cwd` alone Herdr opens
  one the hooks cannot attribute to this session.
- Clean up one workspace at a time: each lane's workspace, then the primary if this session created
  it. Never use `--group`. When a close asks, accept that prompt.
- Read the workspace and root pane IDs from the JSON that `worktree create` returns
  (`.result.workspace.workspace_id`, `.result.root_pane.pane_id`); never predict them.
- `<lane-name>` matches `[a-z][a-z0-9_-]{0,31}` and is new: the hooks let a session prompt only the
  agents it started, and they ask before claiming a name another agent holds.
- Start Claude for an implementation lane, even from a Codex session. Codex keeps a linked
  worktree's Git directory read-only inside its sandbox (openai/codex#14338), so a Codex lane
  cannot commit there without approval. Lanes run on Sonnet at medium effort to save usage; pass
  exactly `-- --model sonnet --effort medium` and nothing else after `--` (the lane starts an
  Opus subagent to review Codex-written code, see
  [herdr-delegation](../../herdr-delegation/SKILL.md)): other agent arguments ask, since they
  could switch off the child's sandbox or approvals.
- The brief follows [herdr-delegation](../../herdr-delegation/SKILL.md) and is self-contained: the
  Issue body and the approved plan text, not only their numbers or links, the lane scope, delivery
  authority (commit, push, and open a PR; never merge), and the reply format.
- A linked worktree session cannot write another repository's `.git`, and this session cannot
  fetch another repository for it, so the lane fetches and rebases onto its base before editing.
- Herdr places the checkout under its `worktrees.directory`; do not pass `--path` without a reason.
- Merged task worktrees and branches, in this repository and every repository with a Herdr task
  worktree, are removed by the parent running `cleanup_worktrees.py` by its absolute path with the
  home directory expanded, as shown in the rendered `excludedCommands` entry, after the user merges,
  or at the next Claude session start (`--dry-run` previews): only when a merged pull request's head
  is the branch tip and the tree is clean, and the primary checkout's `main` then fast-forwards.
  It also closes an agent-created primary workspace when no linked worktrees or agents remain;
  user-created workspaces stay open. `--dry-run` previews both removals and closures.
  Do not remove lane worktrees by hand with `herdr worktree remove` or pull by hand. An abandoned worktree is
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
