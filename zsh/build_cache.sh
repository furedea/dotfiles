#!/bin/bash
# Embedded Zsh expands the quoted positional parameters.
# shellcheck disable=SC2016
set -euxCo pipefail
cd "$(dirname "$0")"

function usage() {
  cat <<EOF >&2
Description:
    Build caches used during interactive Zsh startup.

Usage:
    $0 <ZSH_BIN> <ZSHRC> <ZCOMPDUMP>
EOF
  exit 1
}

function main() {
  (($# == 3)) || usage

  readonly ZSH_BIN="$1"
  readonly ZSHRC="$2"
  readonly ZCOMPDUMP="$3"

  mkdir -p "$(dirname "$ZCOMPDUMP")"
  rm -f -- "$ZCOMPDUMP" "$ZCOMPDUMP.zwc"
  "$ZSH_BIN" -c \
    'autoload -Uz compinit; compinit -i -d "$1"' \
    _ "$ZCOMPDUMP"
  "$ZSH_BIN" -fc 'zcompile -M "$1"' _ "$ZCOMPDUMP"
  "$ZSH_BIN" -fc 'zcompile -R "$1"' _ "$ZSHRC"
}

main "$@"
