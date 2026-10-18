#!/bin/bash
set -euCo pipefail

function usage() {
  cat <<EOF >&2
Description:
    Pin the moshi-hook Nix package to the latest upstream release.
    Prints the new version on update; exits 3 when the pin is already current.

Usage:
    $0 [PACKAGE_FILE]

Options:
    --help, -h: print this
EOF
  exit 1
}

readonly CDN_URL="${MOSHI_CDN_URL:-https://cdn.getmoshi.app/hook}"
readonly ASSET="moshi-hook_Darwin_arm64.tar.gz"
readonly NO_UPDATE_STATUS=3
readonly PACKAGE_PATH="nix/packages/moshi_hook.nix"

function fail() {
  printf 'update_moshi_hook: %s\n' "$1" >&2
  exit 1
}

function fetch() {
  curl --fail --silent --show-error --location --retry 3 "$CDN_URL/$1"
}

function latest_version() {
  local _tag
  _tag="$(fetch latest/version.txt)"
  if [[ ! "$_tag" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
    fail "unexpected latest version: $_tag"
  fi
  printf '%s\n' "${BASH_REMATCH[1]}"
}

function pinned_version() {
  sed -n 's/^  version = "\(.*\)";$/\1/p' "$1"
}

function is_newer() {
  [[ "$1" != "$2" ]] &&
    [[ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -n 1)" == "$1" ]]
}

function asset_hash() {
  local _hex
  _hex="$(fetch "v$1/checksums.txt" |
    awk -v asset="$ASSET" '$2 == asset && length($1) == 64 && $1 ~ /^[0-9a-f]+$/ { print $1 }')"
  if [[ -z "$_hex" ]]; then
    fail "no $ASSET checksum for v$1"
  fi
  local _escaped="" _i
  for ((_i = 0; _i < ${#_hex}; _i += 2)); do
    _escaped+="\\x${_hex:_i:2}"
  done
  printf 'sha256-%s\n' "$(printf '%b' "$_escaped" | base64)"
}

function rewrite_package() {
  local _file="$1"
  local _content
  _content="$(sed \
    -e "s|^  version = \".*\";$|  version = \"$2\";|" \
    -e "s|^    hash = \".*\";$|    hash = \"$3\";|" \
    "$_file")"
  printf '%s\n' "$_content" >|"$_file"
}

function main() {
  if [[ "$#" -gt 1 ]]; then
    usage
  fi
  case "${1:-}" in
    --help | -h) usage ;;
  esac

  local _file="${1:-$(dirname "$0")/../../$PACKAGE_PATH}"
  local _current _latest _hash
  _current="$(pinned_version "$_file")"
  if [[ -z "$_current" ]]; then
    fail "no version pin in $_file"
  fi
  _latest="$(latest_version)"
  if ! is_newer "$_latest" "$_current"; then
    exit "$NO_UPDATE_STATUS"
  fi

  _hash="$(asset_hash "$_latest")"
  rewrite_package "$_file" "$_latest" "$_hash"
  printf '%s\n' "$_latest"
}

main "$@"
