#!/usr/bin/env zsh
setopt ERR_EXIT NO_UNSET NO_CLOBBER PIPE_FAIL

function usage() {
  cat <<EOF >&2
Description:
    Build caches used during interactive Zsh startup.

Usage:
    $0 <ZSHRC> <ZCOMPDUMP>
EOF
  exit 1
}

function main() {
  (($# == 2)) || usage

  local _zshrc="$1"
  local _zcompdump="$2"

  mkdir -p "${_zcompdump:h}"
  rm -f -- "$_zcompdump" "$_zcompdump.zwc"
  autoload -Uz compinit
  compinit -i -d "$_zcompdump"
  zcompile -M "$_zcompdump"
  zcompile -R "$_zshrc"
}

main "$@"
