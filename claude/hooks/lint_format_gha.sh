#!/bin/bash

# lint_format_gha.sh
# Lint GitHub Actions workflow files via actionlint.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

case "$FILE_PATH" in
  */.github/workflows/*.yml | */.github/workflows/*.yaml) ;;
  *)
    exit 0
    ;;
esac

require_cmd actionlint

actionlint -oneline "$FILE_PATH" 2>&1 || {
  echo "❌ actionlint failed for $FILENAME"
  exit 1
}
echo "✅ actionlint completed for $FILENAME"
