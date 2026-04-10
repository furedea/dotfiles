#!/bin/bash

# lint_format_json_toml.sh
# Format JSON and TOML files via dprint.

set -e
# shellcheck source=lint_format.sh
source "$(dirname "$0")/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd dprint

FILE_DIR=$(dirname "$FILE_PATH")
FILE_BASE=$(basename "$FILE_PATH")
# dprint resolves config from CWD; cd to the file's directory and override includes.
(cd "$FILE_DIR" &&
	dprint fmt --config "$HOME/dprint.json" \
		--includes-override "$FILE_BASE" \
		--allow-no-files) 2>&1 || {
	echo "❌ dprint fmt failed for $FILENAME"
	exit 1
}
echo "✅ dprint completed for $FILENAME"
