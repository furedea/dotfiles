#!/bin/bash

# lint_format_sh.sh
# Format and lint Bash / sh scripts via shfmt and shellcheck.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd shfmt
shfmt -w "$FILE_PATH" 2>&1 || {
  echo "❌ shfmt failed for $FILENAME"
  exit 1
}
echo "✅ shfmt completed for $FILENAME"

require_cmd shellcheck
shellcheck -x -P SCRIPTDIR "$FILE_PATH" 2>&1 || {
  echo "❌ shellcheck failed for $FILENAME"
  exit 1
}
echo "✅ shellcheck completed for $FILENAME"
