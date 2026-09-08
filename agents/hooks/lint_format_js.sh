#!/usr/bin/env bash

# lint_format_js.sh
# Quality Loop: format (oxfmt) -> auto-fix (oxlint --fix) -> emit residual
# warnings/errors as PostToolUse additionalContext JSON. Always exits 0.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd oxfmt
run_quality_step "oxfmt format" oxfmt --write "$FILE_PATH"

require_cmd oxlint
run_quality_step "oxlint fix" oxlint --fix "$FILE_PATH"

run_quality_step "oxlint lint" oxlint --deny-warnings "$FILE_PATH"
