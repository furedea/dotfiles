#!/usr/bin/env bash

# lint_format_tex.sh
# Quality Loop: tex-fmt -> capture residual chktex diagnostics as PostToolUse
# additionalContext JSON. Always exits 0.
# Handles .tex, .cls, .sty (format + lint) and .bib (format only).

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

EXTENSION="${FILE_PATH##*.}"

require_cmd tex-fmt
run_quality_step "tex-fmt format" tex-fmt "$FILE_PATH"

# chktex does not support .bib files.
[ "$EXTENSION" = "bib" ] && exit 0

require_cmd chktex
# chktex exits 0 even with warnings; rely on non-empty stdout as the signal.
LINT_STATUS=0
VIOLATIONS=$(chktex -q -n22 -n30 "$FILE_PATH" 2>&1) || LINT_STATUS=$?
if [ "$LINT_STATUS" -ne 0 ]; then
  emit_quality_failure "chktex lint" "$LINT_STATUS" "$VIOLATIONS"
elif [ -n "$VIOLATIONS" ]; then
  emit_post_tool_context "Quality check failed"$'\n'"chktex lint · $FILE_PATH · exit 0"$'\n'"Diagnostics: $VIOLATIONS"
fi
