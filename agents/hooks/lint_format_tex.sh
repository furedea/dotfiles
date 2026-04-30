#!/bin/bash

# lint_format_tex.sh
# Format and lint TeX files via tex-fmt and chktex.
# Handles .tex, .cls, .sty (format + lint) and .bib (format only).

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

EXTENSION="${FILE_PATH##*.}"

require_cmd tex-fmt
tex-fmt "$FILE_PATH" 2>&1 || {
  echo "❌ tex-fmt failed for $FILENAME"
  exit 1
}
echo "✅ tex-fmt completed for $FILENAME"

# chktex does not support .bib files.
[ "$EXTENSION" = "bib" ] && exit 0

require_cmd chktex
chktex -q -n22 -n30 "$FILE_PATH" 2>&1 || {
  echo "❌ chktex failed for $FILENAME"
  exit 1
}
echo "✅ chktex completed for $FILENAME"
