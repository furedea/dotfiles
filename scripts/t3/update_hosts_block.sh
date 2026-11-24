#!/usr/bin/env bash
set -euo pipefail

# Activation runs with a minimal PATH, so every external tool comes from the caller-given TOOLS_PATH.
readonly TOOLS_PATH="${TOOLS_PATH:?TOOLS_PATH is required}"
export PATH="$TOOLS_PATH"

readonly BEGIN_MARKER="# BEGIN t3-telemetry-block (managed by dotfiles; do not edit)"
readonly END_MARKER="# END t3-telemetry-block"

function usage() {
  cat <<EOF2
Description:
    Rewrite the marked block of a hosts file so that each host resolves to 0.0.0.0 and ::.
    Lines outside the block are never changed. A missing block is appended; an unchanged
    file is not written. The file stays unchanged, with exit status 1, when it is not a
    regular file or when the markers are duplicated, unpaired, or in the wrong order.

Usage:
    $0 <HOSTS_FILE> <HOST>...

Environment:
    TOOLS_PATH: PATH for every external tool the script runs (required)

Options:
    --help, -h: print this
EOF2
}

function main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
  fi
  if [[ "$#" -lt 2 ]]; then
    usage >&2
    exit 1
  fi

  local _file="$1"
  shift
  if [[ ! -f "$_file" || -L "$_file" ]]; then
    echo "update_hosts_block: $_file is not a regular file" >&2
    return 1
  fi

  local _updated
  _updated=$(render "$_file" "$@") || return 1
  local _current
  _current=$(
    cat "$_file"
    printf x
  )
  # Both sides carry the sentinel x, so trailing newlines take part in the comparison.
  if [[ "$_updated"$'\n'x == "$_current" ]]; then
    return 0
  fi
  replace_file "$_file" "$_updated"
}

function block_text() {
  local _host
  printf '%s\n' "$BEGIN_MARKER"
  for _host in "$@"; do
    printf '0.0.0.0 %s\n:: %s\n' "$_host" "$_host"
  done
  printf '%s\n' "$END_MARKER"
}

# Print the new content: the file with its block replaced, or with the block appended.
function render() {
  local _file="$1"
  shift
  local _block
  _block=$(block_text "$@")

  local _line _number=0 _begin=0 _end=0 _begin_line=0 _end_line=0
  while IFS= read -r _line || [[ -n "$_line" ]]; do
    _number=$((_number + 1))
    if [[ "$_line" == "$BEGIN_MARKER" ]]; then
      _begin=$((_begin + 1))
      _begin_line=$_number
    elif [[ "$_line" == "$END_MARKER" ]]; then
      _end=$((_end + 1))
      _end_line=$_number
    fi
  done <"$_file"

  if [[ "$_begin" -eq 0 && "$_end" -eq 0 ]]; then
    append_block "$_file" "$_block"
  elif [[ "$_begin" -eq 1 && "$_end" -eq 1 && "$_begin_line" -lt "$_end_line" ]]; then
    replace_block "$_file" "$_block" "$_begin_line" "$_end_line"
  else
    echo "update_hosts_block: $_file has duplicated or unpaired markers; left unchanged" >&2
    return 1
  fi
}

function append_block() {
  local _file="$1"
  local _block="$2"
  local _content
  _content=$(
    cat "$_file"
    printf x
  )
  _content="${_content%x}"
  printf '%s' "$_content"
  if [[ -n "$_content" && "$_content" != *$'\n' ]]; then
    printf '\n'
  fi
  printf '%s\n' "$_block"
}

function replace_block() {
  local _file="$1"
  local _block="$2"
  local _begin_line="$3"
  local _end_line="$4"
  local _line _number=0
  while IFS= read -r _line || [[ -n "$_line" ]]; do
    _number=$((_number + 1))
    if [[ "$_number" -eq "$_begin_line" ]]; then
      printf '%s\n' "$_block"
    elif [[ "$_number" -lt "$_begin_line" || "$_number" -gt "$_end_line" ]]; then
      printf '%s\n' "$_line"
    fi
  done <"$_file"
}

# Rename a same-directory copy over the file so a reader sees the old or the new content.
function replace_file() {
  local _file="$1"
  local _content="$2"
  local _temporary
  _temporary=$(mktemp "$_file.XXXXXX")
  trap 'rm -f "$_temporary"' EXIT
  cp -p "$_file" "$_temporary"
  printf '%s\n' "$_content" >"$_temporary"
  mv -f "$_temporary" "$_file"
  trap - EXIT
}

main "$@"
