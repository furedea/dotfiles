#!/usr/bin/env bash

# lint_format_py.sh
# Quality Loop: format -> auto-fix -> emit residual violations as PostToolUse
# additionalContext JSON. Always exits 0; cross-file checks live in pre-commit / CI.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

if PROJECT_DIR=$(find_project_root "$(dirname "$FILE_PATH")" pyproject.toml uv.lock); then
  require_cmd uv
  cd "$PROJECT_DIR"
  run_quality_step "ruff format" uv run --frozen ruff format "$FILE_PATH"
  run_quality_step "ruff fix" uv run --frozen ruff check --fix-only --quiet "$FILE_PATH"
  run_quality_step "ruff lint" uv run --frozen ruff check --output-format=concise --quiet "$FILE_PATH"
else
  require_cmd ruff
  run_quality_step "ruff format" ruff format "$FILE_PATH"
  run_quality_step "ruff fix" ruff check --fix-only --quiet "$FILE_PATH"
  run_quality_step "ruff lint" ruff check --output-format=concise --quiet "$FILE_PATH"
fi
