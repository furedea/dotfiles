#!/usr/bin/env bash
set -euo pipefail

function usage() {
  cat <<EOF
Description:
    Apply managed values to a JSON file that T3 Code also writes from its UI.
    A missing or empty file is treated as null. The file is replaced atomically with a
    regular file; when jq fails, the file stays unchanged.

Usage:
    $0 <FILE> <JQ_FILTER> <MANAGED_JSON>

    JQ_FILTER reads the current document and the managed value as \$managed.

Options:
    --help, -h: print this
EOF
}

readonly JQ_BIN="${JQ_BIN:?JQ_BIN is required}"

function main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
  fi
  if [[ "$#" -ne 3 ]]; then
    usage >&2
    exit 1
  fi

  local _file="$1"
  local _filter="$2"
  local _managed="$3"
  local _current="null"
  if [[ -s "$_file" ]]; then
    _current=$(<"$_file")
  fi

  mkdir -p "$(dirname "$_file")"
  local _temporary
  _temporary=$(mktemp "$_file.XXXXXX")
  if ! printf '%s' "$_current" |
    "$JQ_BIN" --argjson managed "$_managed" "$_filter" >"$_temporary" ||
    [[ ! -s "$_temporary" ]]; then
    rm -f "$_temporary"
    return 1
  fi
  chmod 0644 "$_temporary"
  mv -f "$_temporary" "$_file"
}

main "$@"
