# jj Reference

## Core Concepts

- **Revision**: Minimum unit of change. The working copy (`@`) is always one revision — no explicit staging step.
- **Change**: An immutable identifier for a line of work (personal task unit).
  - **Change ID**: Short English word sequence, constant across rewrites (prefix-matchable).
  - **Commit ID**: Hex hash that changes whenever content changes (same as Git hash).
- **Bookmark**: Named pointer to a commit for collaboration (equivalent to a Git branch).

## Rev Syntax

| Symbol | Meaning |
|--------|---------|
| `@` | Current working copy |
| `@-` | Parent of the working copy |
| `x-` / `x+` | Parent / children of revision `x` |
| `<change-id>` | Specific change (prefix-matchable) |
| `<bookmark>` | Tip commit of a bookmark |

Key distinctions:
- `jj new @-` creates a **new sibling change** at the parent level (does NOT navigate there)
- `jj edit @-` moves the working copy to the parent for direct editing

## Revsets

Revset is jj's query language. Use with `-r` on any command (e.g., `jj log -r 'mine()'`).

| Expression | Meaning |
|------------|---------|
| `main..@` | Commits from `main` to working copy |
| `mine()` | Commits by current user |
| `trunk()` | Main branch tip (auto-detected) |
| `~merges()` | Exclude merge commits |
| `conflicts()` | Commits with unresolved conflicts |
| `author(email:<email>)` | Commits by specific author |
| `::<rev>` / `<rev>::` | Ancestors / descendants of `<rev>` |

## Setup

```bash
jj config set --user user.name "Your Name"
jj config set --user user.email "you@example.com"
jj git clone <url>          # Full jj migration
jj git init --colocate      # Coexist with existing Git repo
```

## Daily Commands

| Command | Description |
|---------|-------------|
| `jj status` | Show working copy and parent commit info |
| `jj log [-r <rev>]` | Show commit graph (optionally filtered) |
| `jj diff` | Show working copy diff (syntax-aware via difftastic) |
| `jj show <rev>` | Show diff of a specific revision |
| `jj describe -m "<msg>"` | Set commit message on working copy |
| `jj new [-m "<msg>"]` | Finalize working copy, create new change on top |
| `jj new <rev> [-m "<msg>"]` | Create new change on top of `<rev>` |
| `jj new <rev1> <rev2> ...` | Create merge commit from multiple revisions |
| `jj edit <rev>` | Move working copy to `<rev>` for direct editing |
| `jj restore <file>` | Restore file to its parent revision state |

## Squash / Split / Rebase

| Command | Description |
|---------|-------------|
| `jj squash` | Merge working copy into parent |
| `jj squash -i` | Interactive squash (partial) |
| `jj squash -r <rev> -d <dest>` | Merge `<rev>` into `<dest>` without checkout |
| `jj absorb` | Automatically squash fixup commits into their appropriate parents |
| `jj split` | Split working copy into two consecutive changes |
| `jj split -i` | Interactive split (like `git add -p`) |
| `jj rebase -r <rev> -d <dest>` | Move `<rev>` onto `<dest>` without checkout |
| `jj rebase -b <bm> -d main@origin` | Rebase bookmark branch onto `main@origin` (after fetch) |
| `jj abandon -r <rev>` | Discard a commit |

## Bookmarks

| Command | Description |
|---------|-------------|
| `jj bookmark list` | List all bookmarks |
| `jj bookmark create <name>` | Attach bookmark to working copy |
| `jj bookmark create <name> -r <rev>` | Attach bookmark to specific revision |
| `jj bookmark set <name>` | Move existing bookmark to working copy |
| `jj bookmark move <name> --to <rev>` | Move bookmark to any revision |
| `jj bookmark track <bm> --remote origin` | Track remote bookmark locally |

## Remote

| Command | Description |
|---------|-------------|
| `jj git fetch` | Fetch latest remote state |
| `jj git push` | Push bookmarks to remote |
| `jj git push -c @-` | Create auto-named bookmark on `@-` and push |
| `jj git push --bookmark <name>` | Push specific bookmark (force-pushes if rewritten) |

## Undo / History

| Command | Description |
|---------|-------------|
| `jj undo` | Undo last state-changing operation |
| `jj op log` | Show operation history |
| `jj op restore <op-id>` | Restore state to just after a given operation |

## GitHub PR Workflow

```bash
# Create PR — Option 1: auto-named bookmark
jj git push -c @-

# Create PR — Option 2: explicit name
jj bookmark create feature-name -r @-
jj git push

# Update PR — Option A: add commits (preserve history)
jj new
# ... edit ...
jj git push --bookmark feature-name

# Update PR — Option B: amend commits (rewrite history)
jj edit <target-change>
# ... fix ...
jj new
jj git push --bookmark feature-name   # force-pushes automatically

# Sync with remote
jj git fetch
jj rebase -b feature-name -d main@origin
```

## Conflict Resolution

jj embeds conflicts as markers directly in files — you don't need to resolve them all at once, and the repo stays usable with unresolved conflicts.

```bash
# Option A: resolve using a merge tool (recommended)
jj resolve <file>       # Open configured merge tool for one file
jj resolve --all        # Resolve all conflicted files

# Option B: manually edit conflict markers, then record the resolution
jj new                  # Start a new change on top of the conflict
# ... edit markers in files by hand ...
jj squash               # Merge resolution back into the conflicted commit

# Check remaining conflicts
jj log -r 'conflicts()'
jj status
```

Configure a merge tool in `~/.config/jj/config.toml`:

```toml
[ui]
merge-editor = "vimdiff"   # or "meld", "vscode", etc.
```

## Automation Tips

- Pass `--no-editor` on `describe`, `split`, etc., in headless scripts.
- Use `--template '{id} {description|escape_json}\n'` for JSON-friendly output.
- `jj git push --all` pushes **bookmarks only**, not all revisions.
- Exclude `.jj/**` from file watchers (Vite/Vitest, etc.).
