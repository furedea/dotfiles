#!/usr/bin/env bash

# lint_format_nix.sh
# Quality Loop: nixfmt -> statix --fix -> capture residual statix + deadnix
# diagnostics via PostToolUse additionalContext JSON. Always exits 0.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd nixfmt
run_quality_step "nixfmt format" nixfmt "$FILE_PATH"

require_cmd statix
run_quality_step "statix fix" statix fix "$FILE_PATH"
run_quality_step "statix lint" statix check "$FILE_PATH"

require_cmd deadnix
run_quality_step "deadnix lint" deadnix --fail "$FILE_PATH"
