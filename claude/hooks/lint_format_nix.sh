#!/bin/bash

# lint_format_nix.sh
# Format and lint Nix files via nixfmt, statix, and deadnix.

set -e
# shellcheck source=lint_format.sh
source "$(dirname "$0")/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd nixfmt
nixfmt "$FILE_PATH" 2>&1 || {
	echo "❌ nixfmt failed for $FILENAME"
	exit 1
}
echo "✅ nixfmt completed for $FILENAME"

require_cmd statix
statix check "$FILE_PATH" 2>&1 || {
	echo "❌ statix check failed for $FILENAME"
	exit 1
}
echo "✅ statix completed for $FILENAME"

require_cmd deadnix
# --fail exits non-zero when any dead code is detected.
deadnix --fail "$FILE_PATH" 2>&1 || {
	echo "❌ deadnix detected dead code in $FILENAME"
	exit 1
}
echo "✅ deadnix completed for $FILENAME"
