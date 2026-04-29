# Git commit split (one feature, one commit)

A working tree often accumulates several unrelated changes before anyone gets around to committing — a feature, a fix, a config tweak, some stray TODO. Squashing all of that into one commit destroys the history's usefulness for `git blame`, review, revert, and bisect. The goal of this skill is to look at everything pending, group changes by intent, and emit one Conventional Commits commit per intent — going down to hunk granularity when a single file mixes intents. Optionally each commit can be packaged into its own branch and draft PR.

The work happens in four phases: **mode → inspect → plan → execute**. Always show the plan (commits *and* the branching/PR strategy) and wait for explicit user approval before any branch or commit lands; commits are easy to write and painful to undo, branch pushes and PRs are visible to others, and the small cost of a confirmation step pays for itself.

## Phase 0 — Mode selection

The first decision is *where* the commits will live. There are exactly two delivery modes:

| mode | meaning |
| --- | --- |
| `direct` | Commit on the current branch. No branch creation, no push, no PR. Best when you're already on a feature branch, or when the repo has no protections on the current branch. |
| `pr-per-feature` | Create one branch + one draft PR per commit. Within this mode, the **branching strategy** is a separate sub-decision presented in the plan: `independent` (each branch cut from the base, fully parallel PRs) or `stack` (each branch cut from the previous feature branch, dependent PRs). |

**The mode is always set explicitly by the user. Do not auto-detect it.** Auto-detection (e.g., probing `gh api .../branches/main/protection`) is unreliable across environments, silently picks the wrong workflow when authentication is missing, and can push to a protected branch by accident. The cost of asking is one short message; the cost of guessing wrong is a force-push, a denied push that confuses the user, or an unintended PR.

Resolve the mode in this order:

1. If the user's prompt explicitly names the mode (e.g., "PR に分けて", "branch 切って PR", "1 機能 1PR", "draft PR", "stack PR" → `pr-per-feature`; "main に直接", "ここで commit", "この branch に commit" → `direct`), use that.
2. Otherwise ask **one** short question and wait. Example phrasing:

   > この commit 分割は (a) 現在の branch に直接 commit する `direct` モードと，(b) 1 機能ごとに branch を切って draft PR を出す `pr-per-feature` モード のどちらで進めますか？ `pr-per-feature` の場合は，各 PR を独立に base から切る `independent` か，順番に積む `stack` かも併せて教えてください（迷う場合は `independent` が無難です）．

3. Do not proceed until the user answers. Treat silence/ambiguity as "ask again", not "default to direct".

For `pr-per-feature`, also confirm prerequisites *before* inspecting:

- `gh auth status` — `gh` must be authenticated. If it isn't, surface the failure and stop; ask the user to run `gh auth login`. Do not fall back to `direct` silently.
- `git remote -v` — there must be a push remote (typically `origin`) that points to a host `gh` understands. If absent, stop and report.
- Identify the **base branch** (default branch of the remote) with `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`. This is the PR target for `independent`, and the cut point of the *first* branch in `stack`. Record it as `<base>`.

## Phase 1 — Inspect

Read every pending change before grouping. Skipping this leads to surface-level groupings ("commit each file") that miss the intent.

```bash
git rev-parse --is-inside-work-tree   # bail early if not in a repo
git rev-parse --abbrev-ref HEAD       # note current branch
git status --porcelain=v1             # tracked + untracked, machine-readable
git diff                              # unstaged tracked changes
git diff --staged                     # already-staged changes
```

For each file in `git status`:
- **Modified (` M` / `M `)** — read the diff hunks.
- **Untracked (`??`)** — read the file content with `Read`. If it's small and clearly one feature, plan to add it whole; if it's large and mixes concerns, run `git add -N <file>` so it appears in `git diff` and can be hunk-split.
- **Deleted (` D` / `D `)** — note as a deletion; usually pairs with whatever feature removed it.
- **Renamed/Copied (`R`/`C`)** — keep the rename atomic (don't split a rename across commits).

Do not summarize prematurely. Read the actual changes — names, signatures, behavior — so the grouping reflects what the code does, not what the filenames suggest.

## Phase 2 — Plan

Group hunks into commits by **intent**, not by file. A single commit should answer one question: *what user-visible thing changed, and why?*

### How to group

- Same feature, multiple files → one commit.
- Same file, multiple features → multiple commits via hunk split.
- Pure formatting/whitespace mixed in with logic → split into a separate `style:` commit so the logic commit stays reviewable.
- Generated/lockfile updates (`package-lock.json`, `pnpm-lock.yaml`, `uv.lock`, …) belong with the change that caused them, not in their own commit.
- A test for feature X lives in the same commit as feature X (TSDD-friendly), unless the user has a different convention visible in `git log`.

### Choose the type

Use the standard Conventional Commits types. Pick the one that best describes the *primary* effect of the change.

| type | when to use |
| --- | --- |
| `feat` | new user-visible capability |
| `fix` | bug fix |
| `refactor` | restructure without behavior change |
| `perf` | performance-only change |
| `docs` | documentation only |
| `test` | test-only change (adding/fixing tests for *existing* code) |
| `build` | build system, packaging, deps (`package.json`, `pyproject.toml`, lockfiles) |
| `ci` | CI configuration only (`.github/workflows`, etc.) |
| `chore` | tooling/config that doesn't fit elsewhere |
| `style` | formatting, whitespace, semicolons — no logic change |
| `revert` | reverts a previous commit |

If a commit genuinely combines a feature and its tests, use `feat:` (the tests are part of delivering the feature).

### Choose the scope

Conventional Commits scope is optional. The convention here:

1. If all files in the commit live under one identifiable module/area, use that area's name as scope (typically the directory basename — e.g., `src/auth/login.ts` → `auth`).
2. If the commit spans multiple top-level areas or sits at the repo root, **omit the scope**.
3. Scopes are lowercase, single-word, no slashes.

### Write the subject

- Imperative mood ("add", "fix", "remove" — not "added", "adds", "fixed").
- Lowercase first letter, no trailing period.
- Aim for ≤50 characters; hard cap at 72.
- Describe the change, not the file ("add JWT refresh flow", not "update auth.ts").

### Optional body

Add a body only when the *why* isn't obvious from the subject. Wrap at ~72 columns. Skip it for trivial changes — empty bodies are better than filler.

### Examples

```
feat(auth): add JWT refresh-token rotation
fix(parser): handle empty input without panicking
refactor(db): extract query builder from repository
docs: clarify install steps for Apple Silicon
test(auth): cover refresh-token expiry edge case
build(deps): bump axios from 1.6.0 to 1.7.2
chore: ignore .DS_Store
revert: revert "feat(auth): add JWT refresh-token rotation"
```

### Branch / PR plan (only for `pr-per-feature`)

When the mode is `pr-per-feature`, the commit grouping is only half the plan. The user also needs to see and approve:

- **Branch strategy** — `independent` or `stack`. Recommend `independent` unless the commits build on each other in a way the reviewer needs to follow in order (e.g., commit 2 is a refactor that commit 3 depends on). When in doubt, propose `independent` and explain that `stack` is available if dependencies matter.
- **Branch names** — derived from each commit. Format: `<type>/<kebab-subject>`, e.g., `feat/jwt-refresh-rotation`, `fix/parser-empty-input`. Lowercase, ASCII, no scope inside the branch name. If a name already exists locally or remotely, append `-2`, `-3`, … and surface the collision in the plan.
- **PR base** — for `independent`, every PR targets `<base>` (the remote default branch). For `stack`, PR `n` targets the branch from PR `n-1`; PR 1 targets `<base>`.
- **PR shape** — every PR is created as a **draft** via `gh pr create -df` (`-d` = draft, `-f` = fill title/body from the commit). The user can promote drafts later.

Branch names are not pulled from `<scope>` in the commit message; scope is optional in commits but adds noise to branch names. Pick a kebab-case slug from the subject line.

### Plan presentation

Show the plan as a numbered list, in the order the commits will land. For each commit include the message, the affected files, and — for hunk-split commits — the line ranges or a one-line summary of which hunks. For `pr-per-feature`, also include the branch name and PR base for each entry, and state the branch strategy and base branch up front. Then ask for approval.

**`direct` example:**

```
Mode: direct (commits land on current branch `feature/big-batch`)

Proposed commits (3):

1. feat(auth): add JWT refresh-token rotation
   - src/auth/refresh.ts (new file)
   - src/auth/login.ts (hunks 1-2: wire refresh into login)
   - tests/auth/refresh.test.ts (new file)

2. fix(parser): handle empty input without panicking
   - src/parser/index.ts (hunk 3 only)

3. docs: note refresh-token flow in README
   - README.md

Apply this plan? (yes / edit / cancel)
```

**`pr-per-feature` example:**

```
Mode: pr-per-feature
Strategy: independent  (each PR cut from `main`, no dependencies)
Base branch: main
PR shape: draft (gh pr create -df)

Proposed commits / branches (3):

1. feat(auth): add JWT refresh-token rotation
   branch: feat/jwt-refresh-rotation   →  PR base: main
   - src/auth/refresh.ts (new file)
   - src/auth/login.ts (hunks 1-2)
   - tests/auth/refresh.test.ts (new file)

2. fix(parser): handle empty input without panicking
   branch: fix/parser-empty-input      →  PR base: main
   - src/parser/index.ts (hunk 3 only)

3. docs: note refresh-token flow in README
   branch: docs/refresh-token-readme   →  PR base: main
   - README.md

Apply this plan? (yes / edit / cancel)
```

For `stack`, replace the strategy line and the per-entry PR base accordingly:

```
Strategy: stack  (each PR depends on the previous; merge in order)

1. ...   branch: refactor/extract-query-builder  →  PR base: main
2. ...   branch: feat/repository-cache           →  PR base: refactor/extract-query-builder
3. ...   branch: test/repository-cache-edges     →  PR base: feat/repository-cache
```

If the user requests edits, revise and re-present — never silently change the plan. Treat branch-strategy changes (independent ↔ stack) as a full re-plan; a stack and a parallel set are very different review experiences.

## Phase 3 — Execute

Once the user approves, execute the plan deterministically. The key invariant: **after each commit, regenerate the diff against the new HEAD before building the next partial patch**, because line numbers shift as commits land.

### Setup

```bash
git rev-parse HEAD > /tmp/pre-split-head        # safety net for `git reset --hard` recovery
git rev-parse --abbrev-ref HEAD > /tmp/pre-split-branch   # remember where we started
git reset                                        # clear the index so we start clean
```

Recording the pre-split HEAD is the actual safety net: if anything goes wrong mid-execution, `git reset --hard "$(cat /tmp/pre-split-head)"` undoes every commit this session created. The working tree is preserved by the reset because `git reset` (no `--hard`) only touches the index. The branch name is recorded so `pr-per-feature` can return to it between branches.

For untracked files that need hunk-level splitting, mark them intent-to-add up front so they show up in `git diff`:

```bash
git add -N <new-file>      # only for files needing hunk split
```

For `pr-per-feature` only: confirm the working tree's starting branch is the intended **PR base** for the first iteration. In `independent` mode, this should be `<base>` (the remote default). In `stack` mode, this is the cut point of branch 1 — usually also `<base>`. If the working tree currently sits on a feature branch with the changes, that's fine — the staged work will be carried over to the new branches by `git switch -c` (which creates a branch at the current commit and keeps the working tree).

### Per-commit loop

For each planned commit, in order. Steps marked **(pr-per-feature)** only run in that mode; `direct` skips them.

0. **(pr-per-feature) Create the feature branch before staging.** Cut from the right base so the new branch contains the same working-tree state but starts off the correct commit:
   ```bash
   # independent: every branch is cut from <base>
   git switch -c <branch-name> <base>

   # stack: branch 1 is cut from <base>; branch n>1 is cut from branch n-1
   git switch -c <branch-name> <prev-branch>
   ```
   `git switch -c` preserves the uncommitted working tree, so the diff to be committed travels with you. If the cut point lags the remote `<base>`, run `git fetch origin && git switch -c <branch-name> origin/<base>` instead so the PR doesn't include unrelated commits. After this step the working tree should still show every remaining hunk in `git status`.

1. **Whole-file commits** (most common path):
   ```bash
   git add -- <file1> <file2> ...
   git commit -m "<conventional message>"
   ```
   For deletions, `git add -- <deleted-file>` works too (stages the deletion).

2. **Hunk-level commits** (when one file is split across commits). Resolve `<skill-dir>` to the directory containing this `SKILL.md` — typically `~/.claude/skills/git-commit-split` (Claude Code) or `~/.codex/skills/git-commit-split` (Codex); both point at the same files via dotfiles symlinks, so either form works.
   ```bash
   git diff -U0 --src-prefix=a/ --dst-prefix=b/ -- <file> > /tmp/cur.patch
   <skill-dir>/scripts/build_partial_patch.py \
       /tmp/cur.patch '[{"file": "<file>", "hunks": [1, 3]}]' > /tmp/partial.patch
   git apply --cached --unidiff-zero /tmp/partial.patch
   git commit -m "<conventional message>"
   ```
   - `-U0` produces zero-context hunks. Default `-U3` merges adjacent edits within 3 lines into one `@@` hunk, which is exactly the case where two intents (say a fix and a new function added 2 lines apart) can no longer be split. Zero-context diffs keep every edit as its own hunk.
   - `git apply --unidiff-zero` is required to consume zero-context patches; without it `git apply` rejects them as ambiguous.
   - `--src-prefix=a/ --dst-prefix=b/` overrides any local `diff.mnemonicPrefix` config so the patch always uses the `a/`/`b/` prefixes that `git apply` defaults to.
   - `git diff` is regenerated *every iteration* so hunk numbering reflects the current HEAD; previously committed hunks disappear and remaining hunks are renumbered automatically. Always rebuild the patch from a fresh `git diff` — never reuse `cur.patch` across commits.

   **Anti-pattern: don't rewrite the file in place.** A tempting shortcut is to `git stash`, rewrite `<file>` to a partial state, commit, then `git stash pop` to restore the rest. This works for one or two commits but conflicts as soon as later commits overlap the same lines, and it loses the property that each commit is a real subset of the original diff. Stick to `git apply --cached` against fresh diffs.

3. **Mixed commit** (some whole files + some partial hunks): run the partial-apply step first, then `git add` the whole-file additions, then commit once.

4. **(pr-per-feature) Push the branch and open a draft PR:**
   ```bash
   git push -u origin <branch-name>
   gh pr create -df --base <pr-base>
   ```
   - `-d` makes it a draft, `-f` fills the title and body from the commit. The user requested draft so reviewers know it's not yet ready and so CI can be cheap.
   - `<pr-base>` is `<base>` for `independent` and the previous branch for `stack`.
   - If `gh pr create` fails (e.g., the repo doesn't allow drafts on this plan, or the branch was just pushed and `gh` hasn't seen it), surface the error and pause — don't try clever recovery. The branch and commit are safe; the user can run `gh pr create` themselves.

5. **(pr-per-feature) Move to the next iteration's starting point.** After pushing and opening the PR, the working tree may still have remaining hunks for later commits. To prepare for the next iteration:
   - **independent:** `git switch <base>` (or `git switch "$(cat /tmp/pre-split-branch)"` if the user started off the base) to return to the cut point. The remaining uncommitted changes travel with you. The next iteration's step 0 will cut a fresh branch from here.
   - **stack:** stay on the current branch — the next iteration's step 0 will cut its branch from here.

   Do not delete the just-pushed branch locally; the PR points at it and the user may need to amend.

### Post-commit verification

After the loop:

```bash
git status                                 # should be clean (or only have intentionally-left changes)
git log --oneline -n <N>                   # confirm N commits landed in order (direct mode)
```

For `pr-per-feature`, also list each branch and its PR so the user can act on the result:

```bash
gh pr list --author @me --state open --json number,title,headRefName,baseRefName,url \
    --limit 20
```

Report each branch name, the PR number/URL, and the PR base. For `stack`, remind the user the merge order must follow the stack from bottom to top (PR 1 → PR 2 → …) so the bases keep pointing at landed commits.

If `git status` still shows pending changes when the plan claimed to cover everything, **stop and report** — don't paper over it. Likely causes: a hunk that didn't apply (line drift), an `.gitignore` masking a file, or a missed binary file.

### Recovery

If anything goes wrong mid-execution, the safety stash from setup gives you a way back. To abort and restore:

```bash
git reset --hard <pre-split-HEAD>          # only if commits already landed and need undoing
git stash list                             # find the safety stash
git stash apply stash@{N}                  # restore the original working tree
```

Only run `git reset --hard` after confirming with the user, since it's destructive. Prefer `git reset --soft` if commits need rewriting rather than discarding.

## Edge cases

- **Pre-commit hook failure.** A failed hook means the commit didn't land. Read the hook output, fix the issue (typically a lint/format problem), `git add` the fix, and **create a new commit** — never `--amend` an attempted-but-failed commit, because the previous successful commit would be modified instead. In `pr-per-feature` this also means the branch's first push hasn't happened yet, so retry the commit before pushing.
- **Push rejected on the base branch.** If `direct` mode tries to push (it shouldn't — this skill never pushes in `direct` mode) or `pr-per-feature` is somehow asked to push to the base branch, stop and surface it. The protected base is exactly why `pr-per-feature` exists; never `--force` past a protection rule.
- **`gh` not authenticated / no remote.** Already caught in Phase 0, but if it surfaces mid-execution (token expired, network blip), pause and tell the user. The local commit is intact; they can re-auth and resume by running `git push -u origin <branch-name>` and `gh pr create -df --base <pr-base>` themselves.
- **Branch name collision.** If `git switch -c <branch-name> <base>` fails because the branch already exists locally, append `-2`, `-3`, … to the slug and update the plan entry before retrying. Same for remote collisions surfaced by `git push` (`! [rejected] ... (fetch first)`).
- **Stack base lags after a previous PR is merged.** Out of scope for this skill — it doesn't merge or rebase stacks. If the user merges PR 1 themselves while later PRs are still open, those PRs' bases will rebase on the next push; that's the user's call, not this skill's.
- **Nothing to commit.** If `git status` is clean before starting, say so and stop. Don't invent commits.
- **Detached HEAD.** Warn the user — committing on detached HEAD risks orphaning the work. Suggest `git switch -c <branch>` first. In `pr-per-feature` this is a hard stop; the mode requires a named branch to push from.
- **Merge in progress** (`.git/MERGE_HEAD` exists). Don't try to split — the user is mid-merge. Surface this and ask.
- **Submodule pointer changes.** Treat as a single file; usually goes in a `chore(submodule):` or with the feature that bumped it.
- **Binary files.** No hunk-level split possible — commit whole or skip.
- **One giant change that genuinely is one feature.** Don't fabricate splits. One commit is fine if the work is one cohesive thing; report that and commit once. In `pr-per-feature` this still means one branch + one PR — the mode doesn't manufacture extra branches.
- **User commits in non-English.** Detect the language used in recent `git log --oneline -n 20` output. If recent history is non-English, match it; otherwise default to English (the Conventional Commits convention). Branch names stay ASCII regardless, since some hosts and tools choke on non-ASCII refs.

## Helper script

`scripts/build_partial_patch.py` filters a unified diff to a selected subset of hunks. Run it via `python3` — it has no third-party dependencies. The script's `--help`-equivalent is its module docstring; read the file directly for the JSON selection schema.
