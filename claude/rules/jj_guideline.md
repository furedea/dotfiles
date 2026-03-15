# Jujutsu (jj) Guidelines

jj is a DVCS that auto-commits the working copy as a revision. Prefer jj over Git for all VCS operations.

## Core Concepts

- **Revision**: The minimum unit of change. The working copy (`@`) is always one revision; no explicit staging step.
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
| `author(email:<email>)` | Commits by specific author |
| `::<rev>` / `<rev>::` | Ancestors / descendants of `<rev>` |

## Notes

- `jj git push --all` pushes **bookmarks only**, not all revisions.
- Exclude `.jj/**` from file watchers (Vite/Vitest, etc.).
