#!/usr/bin/env bash

# lint_format_md.sh
# Quality Loop: autocorrect --fix -> prettierd (atomic swap via stdin/stdout).
# Format-only; emits execution errors as context. Always exits 0.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd autocorrect
run_quality_step "autocorrect format" autocorrect --fix "$FILE_PATH"

require_cmd prettierd
TMPFILE=$(mktemp)
ERROR_FILE=$(mktemp)
# shellcheck disable=SC2094
if PRETTIERD_DEFAULT_CONFIG="$HOME/.prettierrc" \
  prettierd "$FILE_PATH" <"$FILE_PATH" >"$TMPFILE" 2>"$ERROR_FILE"; then
  mv "$TMPFILE" "$FILE_PATH"
else
  FORMAT_STATUS=$?
  emit_quality_failure "prettierd format" "$FORMAT_STATUS" "$(cat "$ERROR_FILE")"
  rm -f "$TMPFILE"
fi
rm -f "$ERROR_FILE"
