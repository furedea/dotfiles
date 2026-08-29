#!/usr/bin/env bash
set -euxCo pipefail
cd "$(dirname "$0")"

function usage() {
  cat <<EOF >&2
Description:
    Start the Hister server with its access token from the macOS Keychain.

Usage:
    $0 <HISTER_BIN> <KEYCHAIN_ACCOUNT>

Options:
    --help, -h: print this
EOF
  exit 1
}

readonly KEYCHAIN_SERVICE="${HISTER_KEYCHAIN_SERVICE:-org.furedea.hister.access-token}"
readonly SECURITY_BIN="${HISTER_SECURITY_BIN:-/usr/bin/security}"

function main() {
  if [[ "$#" -ne 2 ]]; then
    usage
  fi

  local _hister_bin="$1"
  local _keychain_account="$2"

  set +x
  if ! IFS= read -r HISTER__APP__ACCESS_TOKEN < <(
    "$SECURITY_BIN" find-generic-password \
      -a "$_keychain_account" \
      -s "$KEYCHAIN_SERVICE" \
      -w 2>/dev/null
  ) || [[ -z "${HISTER__APP__ACCESS_TOKEN:-}" ]]; then
    printf '%s\n' \
      'Hister access token is unavailable in the macOS Keychain.' >&2
    exit 1
  fi
  export HISTER__APP__ACCESS_TOKEN
  set -x

  exec "$_hister_bin" listen
}

main "$@"
