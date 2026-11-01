#!/bin/bash
set -euCo pipefail

function usage() {
  cat <<EOF >&2
Description:
    Pin the codex Nix package to the latest stable upstream release.
    Prints the new version on update; exits 3 when the pin is already current.

Usage:
    $0 [PACKAGE_FILE]

Options:
    --help, -h: print this
EOF
  exit 1
}

readonly RELEASES_URL="${CODEX_RELEASES_URL:-https://api.github.com/repos/openai/codex/releases?per_page=100}"
readonly ASSET="codex-package-aarch64-apple-darwin.tar.gz"
readonly NO_UPDATE_STATUS=3
readonly PACKAGE_PATH="nix/packages/codex.nix"

function fail() {
  printf 'update_codex: %s\n' "$1" >&2
  exit 1
}

function fetch_releases() {
  local _auth=()
  if [[ -n "${GH_TOKEN:-}" ]]; then
    _auth=(--header "Authorization: Bearer $GH_TOKEN")
  fi
  curl --fail --silent --show-error --location --retry 3 ${_auth[@]+"${_auth[@]}"} "$RELEASES_URL"
}

function latest_version() {
  local _versions
  _versions="$(jq --raw-output '.[]
    | select(.draft == false and .prerelease == false)
    | .tag_name
    | capture("^rust-v(?<version>[0-9]+\\.[0-9]+\\.[0-9]+)$")
    | .version' <<<"$1")"
  if [[ -z "$_versions" ]]; then
    fail "no stable rust-vX.Y.Z release found"
  fi
  sort -V <<<"$_versions" | tail -n 1
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
  _hex="$(jq --raw-output --arg tag "rust-v$2" --arg asset "$ASSET" '.[]
    | select(.tag_name == $tag)
    | .assets[]
    | select(.name == $asset)
    | .digest // empty
    | select(test("^sha256:[0-9a-f]{64}$"))
    | ltrimstr("sha256:")' <<<"$1")"
  if [[ -z "$_hex" ]]; then
    fail "no $ASSET sha256 digest for rust-v$2"
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
  local _current _releases _latest _hash
  _current="$(pinned_version "$_file")"
  if [[ -z "$_current" ]]; then
    fail "no version pin in $_file"
  fi
  _releases="$(fetch_releases)"
  _latest="$(latest_version "$_releases")"
  if ! is_newer "$_latest" "$_current"; then
    exit "$NO_UPDATE_STATUS"
  fi

  _hash="$(asset_hash "$_releases" "$_latest")"
  rewrite_package "$_file" "$_latest" "$_hash"
  printf '%s\n' "$_latest"
}

main "$@"
