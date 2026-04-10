#!/bin/bash

# lint_format_py.sh
# Format and lint Python files via ruff.
# In a uv project: uses uv run --frozen ruff (project-pinned version).
# Standalone: uses global ruff.

set -e
# shellcheck source=lint_format.sh
source "$(dirname "$0")/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

if PROJECT_DIR=$(find_project_root "$(dirname "$FILE_PATH")" pyproject.toml uv.lock); then
	require_cmd uv
	cd "$PROJECT_DIR"
	uv run --frozen ruff format "$FILE_PATH" 2>&1 || {
		echo "❌ ruff format failed for $FILENAME"
		exit 1
	}
	uv run --frozen ruff check "$FILE_PATH" 2>&1 || {
		echo "❌ ruff check failed for $FILENAME"
		exit 1
	}
else
	require_cmd ruff
	ruff format "$FILE_PATH" 2>&1 || {
		echo "❌ ruff format failed for $FILENAME"
		exit 1
	}
	ruff check "$FILE_PATH" 2>&1 || {
		echo "❌ ruff check failed for $FILENAME"
		exit 1
	}
fi

echo "✅ ruff completed for $FILENAME"
