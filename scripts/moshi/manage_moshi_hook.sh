#!/bin/bash
set -euCo pipefail
cd "$(dirname "$0")"

function usage() {
  cat <<EOF >&2
Description:
    Manage the Keychain-backed Moshi host lifecycle.

Usage:
    $0 serve

Options:
    --help, -h: print this
EOF
  exit 1
}

readonly JQ_BIN="${JQ_BIN:-jq}"
readonly MOSHI_HOOK_BIN="${MOSHI_HOOK_BIN:-moshi-hook}"
readonly SLEEP_BIN="${SLEEP_BIN:-sleep}"
readonly RETRY_SECONDS="${MOSHI_RETRY_SECONDS:-30}"

function pairing_available() {
  "$MOSHI_HOOK_BIN" status --json 2>/dev/null |
    "$JQ_BIN" -e \
      '.paired == true and .secretStore == "keychain"' >/dev/null
}

function wait_for_pairing() {
  until pairing_available; do
    "$SLEEP_BIN" "$RETRY_SECONDS"
  done
}

function serve() {
  wait_for_pairing
  exec "$MOSHI_HOOK_BIN" serve
}

function main() {
  if [[ "$#" -ne 1 ]]; then
    usage
  fi

  case "$1" in
    serve)
      serve
      ;;
    --help | -h | *)
      usage
      ;;
  esac
}

main "$@"
