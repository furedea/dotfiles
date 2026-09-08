#!/usr/bin/env bash

# lint_format_rs.sh
# Quality Loop: rustfmt only. Cargo clippy is cross-file (whole crate) and
# runs at pre-commit / CI, not per file.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd rustfmt
run_quality_step "rustfmt format" rustfmt "$FILE_PATH"
