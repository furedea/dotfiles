#!/bin/bash

# lint_format_txt.sh
# Correct text files via autocorrect (CJK spacing etc.).

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd autocorrect
autocorrect --fix "$FILE_PATH" 2>&1 || {
  echo "❌ autocorrect failed for $FILENAME"
  exit 1
}
echo "✅ autocorrect completed for $FILENAME"
