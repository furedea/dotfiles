#!/usr/bin/env bash

# lint_format_sh.sh
# Quality Loop: format (shfmt -w) -> emit residual shellcheck diagnostics as
# PostToolUse additionalContext JSON. Always exits 0.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd shfmt
run_quality_step "shfmt format" shfmt -w "$FILE_PATH"

require_cmd shellcheck
run_quality_step "shellcheck lint" shellcheck -x -P SCRIPTDIR "$FILE_PATH"
