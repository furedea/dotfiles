#!/usr/bin/env bash
set -euCo pipefail

function usage() {
  cat <<EOF >&2
Description:
    Run Git's SSH signer against the local 1Password SSH agent.

Usage:
    $0 <ssh-keygen arguments>
EOF
  exit 1
}

function main() {
  [[ "$#" -gt 0 && "$1" != --help && "$1" != -h ]] || usage
  if [[ "${1:-}" == -Y && "${2:-}" == sign ]]; then
    attach_onepassword_agent || :
  fi
  exec ssh-keygen "$@"
}

function attach_onepassword_agent() {
  local _socket="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
  # Attach only this user's own socket; never scan arbitrary sockets.
  [[ -S "$_socket" && ! -L "$_socket" ]] || return 1
  [[ "$(stat -f '%u' "$_socket")" == "$(id -u)" ]] || return 1
  export SSH_AUTH_SOCK="$_socket"
}

main "$@"
