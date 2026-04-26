#!/bin/bash

# lint_format_js.sh
# Format and lint JavaScript/TypeScript files via oxfmt and oxlint.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd oxfmt
oxfmt --write "$FILE_PATH" 2>&1 || {
  echo "❌ oxfmt failed for $FILENAME"
  exit 1
}
echo "✅ oxfmt completed for $FILENAME"

require_cmd oxlint
oxlint "$FILE_PATH" 2>&1 || {
  echo "❌ oxlint failed for $FILENAME"
  exit 1
}
echo "✅ oxlint completed for $FILENAME"
