#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"

function usage() {
  cat <<EOF >&2
Description:
    Manage the Keychain-backed Moshi host lifecycle.

Usage:
    $0 serve
    $0 restart-after-update
    $0 migrate-homebrew-service

Options:
    --help, -h: print this
EOF
  exit 1
}

readonly BREW_BIN="${BREW_BIN:-/opt/homebrew/bin/brew}"
readonly DEFAULT_LEGACY_SERVICE_FILE="$HOME/Library/LaunchAgents/homebrew.mxcl.moshi-hook.plist"
readonly DEFAULT_RUNTIME_STATE_FILE="$HOME/.local/state/moshi-hook/runtime_path"
readonly JQ_BIN="${JQ_BIN:-jq}"
readonly LAUNCHCTL_BIN="${LAUNCHCTL_BIN:-/bin/launchctl}"
readonly LEGACY_SERVICE_FILE="${MOSHI_LEGACY_SERVICE_FILE:-$DEFAULT_LEGACY_SERVICE_FILE}"
readonly MKDIR_BIN="${MKDIR_BIN:-/bin/mkdir}"
readonly MOSHI_HOOK_BIN="${MOSHI_HOOK_BIN:-/opt/homebrew/bin/moshi-hook}"
readonly REALPATH_BIN="${REALPATH_BIN:-realpath}"
readonly SLEEP_BIN="${SLEEP_BIN:-sleep}"
readonly RETRY_SECONDS="${MOSHI_RETRY_SECONDS:-30}"
readonly RUNTIME_STATE_FILE="${MOSHI_RUNTIME_STATE_FILE:-$DEFAULT_RUNTIME_STATE_FILE}"
readonly SERVICE_LABEL="${MOSHI_SERVICE_LABEL:-org.nix-community.home.moshi-hook}"
readonly USER_ID="${USER_ID:-$(/usr/bin/id -u)}"

function pairing_available() {
  "$MOSHI_HOOK_BIN" status --json 2>/dev/null |
    "$JQ_BIN" -e \
      '.paired == true and .secretStore == "keychain"' >/dev/null
}

function runtime_available() {
  "$MOSHI_HOOK_BIN" probe --json 2>/dev/null |
    "$JQ_BIN" -e '
      .running == true
        and .gateway == true
        and ((.hostId | type) == "string")
        and ((.hostId | length) > 0)
    ' >/dev/null
}

function wait_for_pairing() {
  until pairing_available; do
    "$SLEEP_BIN" "$RETRY_SECONDS"
  done
}

function wait_for_runtime() {
  until runtime_available; do
    "$SLEEP_BIN" "$RETRY_SECONDS"
  done
}

function current_runtime_path() {
  "$REALPATH_BIN" "$MOSHI_HOOK_BIN"
}

function runtime_is_current() {
  local _recorded_runtime

  if [[ ! -f "$RUNTIME_STATE_FILE" ]]; then
    return 1
  fi

  read -r _recorded_runtime <"$RUNTIME_STATE_FILE"
  [[ "$_recorded_runtime" == "$(current_runtime_path)" ]]
}

function record_runtime() {
  "$MKDIR_BIN" -p "${RUNTIME_STATE_FILE%/*}"
  current_runtime_path >|"$RUNTIME_STATE_FILE"
}

function serve() {
  wait_for_pairing
  record_runtime
  exec "$MOSHI_HOOK_BIN" serve
}

function restart_after_update() {
  if runtime_is_current; then
    return
  fi

  wait_for_pairing
  "$LAUNCHCTL_BIN" kickstart -k "gui/$USER_ID/$SERVICE_LABEL"
  wait_for_runtime
  record_runtime
}

function migrate_homebrew_service() {
  if [[ ! -e "$LEGACY_SERVICE_FILE" ]]; then
    return
  fi

  "$BREW_BIN" services stop rjyo/moshi/moshi-hook
}

function main() {
  if [[ "$#" -ne 1 ]]; then
    usage
  fi

  case "$1" in
    serve)
      serve
      ;;
    restart-after-update)
      restart_after_update
      ;;
    migrate-homebrew-service)
      migrate_homebrew_service
      ;;
    --help | -h | *)
      usage
      ;;
  esac
}

main "$@"
