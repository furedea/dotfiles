#!/usr/bin/env bash
set -euCo pipefail

function usage() {
  cat <<EOF >&2
Description:
    Run Git's SSH signer with a local macOS agent fallback.

Usage:
    $0 <ssh-keygen arguments>
EOF
  exit 1
}

function main() {
  [[ "$#" -gt 0 && "$1" != --help && "$1" != -h ]] || usage
  if [[ "${1:-}" == -Y && "${2:-}" == sign && -z "${SSH_AUTH_SOCK:-}" ]]; then
    restore_agent_socket || :
  fi
  exec ssh-keygen "$@"
}

function restore_agent_socket() {
  local _uid _socket
  _uid=$(id -u)
  # Query only this user's Apple-managed agent; never scan arbitrary sockets.
  _socket=$(launchctl print "gui/$_uid/com.openssh.ssh-agent" 2>/dev/null |
    awk '$1 == "path" && $2 == "=" && $3 ~ /\/Listeners$/ { print $3 }') || return 1
  [[ -S "$_socket" && ! -L "$_socket" ]] || return 1
  [[ "$(stat -f '%u' "$_socket")" == "$_uid" ]] || return 1
  export SSH_AUTH_SOCK="$_socket"
}

main "$@"
