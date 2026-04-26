#!/bin/bash

# lint_format_md.sh
# Format Markdown files via autocorrect and prettierd.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd autocorrect
autocorrect --fix "$FILE_PATH" 2>&1 || {
  echo "❌ autocorrect failed for $FILENAME"
  exit 1
}
echo "✅ autocorrect completed for $FILENAME"

require_cmd prettierd
# prettierd has no --write: read from stdin, write to stdout, then swap atomically.
TMPFILE=$(mktemp)
# shellcheck disable=SC2094
if PRETTIERD_DEFAULT_CONFIG="$HOME/.prettierrc" \
  prettierd "$FILE_PATH" <"$FILE_PATH" >"$TMPFILE" 2>&1; then
  mv "$TMPFILE" "$FILE_PATH"
  echo "✅ prettierd completed for $FILENAME"
else
  rm -f "$TMPFILE"
  echo "❌ prettierd failed for $FILENAME"
  exit 1
fi
