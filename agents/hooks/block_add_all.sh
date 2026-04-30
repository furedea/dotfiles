#!/bin/bash
# Claude Code PreToolUse hook: block `git add .`, `git add -A`, `git add --all`.
# Forces explicit staging of files by name so that stray edits, debug prints,
# or secrets cannot be swept into a commit unintentionally.
# Exit code 0 = allow, exit code 2 = block.

set -euCo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Match:
#   git add .
#   git add -A
#   git add --all
# The match requires that the bulk-staging argument be a standalone word
# (bounded by whitespace or end-of-string) so that file paths like `./foo`
# or a filename `allocator.py` are not mistaken for `.` / `--all`.
if echo "$COMMAND" | grep -qE 'git\s+add(\s+[^[:space:]]+)*\s+(\.|-A|--all)(\s|$)'; then
  cat >&2 <<ERRMSG
BLOCKED: bulk \`git add\` detected (\`.\`, \`-A\`, or \`--all\`).

Why: Bulk staging defeats explicit file-by-file review and can include
     unintended changes (stray edits, debug prints, secrets).

What to do:
  Claude Code: Stage files explicitly by path, e.g. \`git add path/to/file\`.
  User: If you intentionally want to stage everything, run the add and
        commit manually in your terminal.
ERRMSG
  exit 2
fi

exit 0
