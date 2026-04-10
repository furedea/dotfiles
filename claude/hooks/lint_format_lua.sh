#!/bin/bash

# lint_format_lua.sh
# Format and lint Lua files via stylua and selene.

set -e
# shellcheck source=lint_format.sh
source "$(dirname "$0")/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd stylua
stylua "$FILE_PATH" 2>&1 || {
	echo "❌ stylua failed for $FILENAME"
	exit 1
}
echo "✅ stylua completed for $FILENAME"

require_cmd selene
# selene 0.25+ only reads selene.toml from CWD (no upward search); walk up manually.
SELENE_DIR=$(find_project_root "$(dirname "$FILE_PATH")" selene.toml) || SELENE_DIR="$(dirname "$FILE_PATH")"
(cd "$SELENE_DIR" && selene "$FILE_PATH") 2>&1 || {
	echo "❌ selene failed for $FILENAME"
	exit 1
}
echo "✅ selene completed for $FILENAME"
