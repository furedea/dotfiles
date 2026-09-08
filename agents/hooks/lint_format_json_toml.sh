#!/usr/bin/env bash

# lint_format_json_toml.sh
# Quality Loop: format JSON/TOML via dprint, then emit residual diagnostics
# as PostToolUse additionalContext JSON. Always exits 0.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd dprint

FILE_DIR=$(dirname "$FILE_PATH")
FILE_BASE=$(basename "$FILE_PATH")
# dprint resolves config from CWD; cd to the file's directory and override includes.
(cd "$FILE_DIR" &&
  run_quality_step "dprint format" dprint fmt --config "$HOME/dprint.json" \
    --includes-override "$FILE_BASE" \
    --allow-no-files)

(cd "$FILE_DIR" &&
  run_quality_step "dprint lint" dprint check --config "$HOME/dprint.json" \
    --includes-override "$FILE_BASE" \
    --allow-no-files)
