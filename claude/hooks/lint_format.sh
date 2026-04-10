#!/bin/bash

# lint_format.sh
# Shared utilities for per-language lint_format hooks.
# Source this file; do not execute it directly.

# Read FILE_PATH from the hook's stdin JSON.
# Sets FILE_PATH and FILENAME globals.
# Exits 0 (skip, silent) when no path is provided; exits 1 when file is missing.
load_file_path() {
	local input
	input=$(cat)
	FILE_PATH=$(echo "$input" | jq -r '.tool_input.file_path // empty')
	[ -z "$FILE_PATH" ] && exit 0
	[ ! -f "$FILE_PATH" ] && {
		echo "File not found: $FILE_PATH"
		exit 1
	}
	# shellcheck disable=SC2034
	# FILENAME is consumed by the sourced per-language hook scripts.
	FILENAME=$(basename "$FILE_PATH")
}

# Walk up from <start_dir> until a file matching any <target> name is found.
# Prints the directory that contains the match and returns 0.
# Returns 1 (prints nothing) when reaching filesystem root without a match.
find_project_root() {
	local dir="$1"
	shift
	while [ "$dir" != "/" ]; do
		for target in "$@"; do
			[ -f "$dir/$target" ] && {
				echo "$dir"
				return 0
			}
		done
		dir=$(dirname "$dir")
	done
	return 1
}

# Assert a command exists; print an error and exit 1 if not found.
require_cmd() {
	command -v "$1" &>/dev/null || {
		echo "❌ $1 not found in PATH"
		exit 1
	}
}
