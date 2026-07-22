#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"

function usage() {
  cat <<EOF >&2
Description:
    Synchronize Nix-managed Herdr plugins.

Usage:
    $0 [<PLUGIN_ID> <GITHUB_SOURCE> <GIT_REF>]...

Options:
    --help, -h: print this
EOF
  exit 1
}

readonly HERDR_BIN="${HERDR_BIN:-herdr}"
readonly JQ_BIN="${JQ_BIN:-jq}"
readonly STATE_FILE="${HERDR_PLUGIN_SYNC_STATE_FILE:-${XDG_STATE_HOME:-${HOME}/.local/state}/home-manager/herdr_plugins}"
plugins_json=""

function validate_arguments() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
  fi
  if (($# % 3 != 0)); then
    usage
  fi
}

function installed_commit() {
  local _plugin_id="$1"
  # shellcheck disable=SC2016
  "$JQ_BIN" -r \
    --arg plugin_id "$_plugin_id" \
    '.result.plugins[]? | select(.plugin_id == $plugin_id) | .source.resolved_commit // empty' \
    <<<"$plugins_json"
}

function is_installed() {
  local _plugin_id="$1"
  # shellcheck disable=SC2016
  "$JQ_BIN" -e \
    --arg plugin_id "$_plugin_id" \
    'any(.result.plugins[]?; .plugin_id == $plugin_id)' \
    >/dev/null \
    <<<"$plugins_json"
}

function is_declared() {
  local _target_plugin_id="$1"
  shift
  while (($# > 0)); do
    if [[ "$1" == "$_target_plugin_id" ]]; then
      return 0
    fi
    shift 3
  done
  return 1
}

function uninstall_removed_plugins() {
  if [[ ! -f "$STATE_FILE" ]]; then
    return
  fi
  while IFS= read -r _plugin_id; do
    if [[ -n "$_plugin_id" ]] &&
      ! is_declared "$_plugin_id" "$@" &&
      is_installed "$_plugin_id"; then
      "$HERDR_BIN" plugin uninstall "$_plugin_id"
    fi
  done <"$STATE_FILE"
}

function install_plugins() {
  while (($# > 0)); do
    local _plugin_id="$1"
    local _source="$2"
    local _git_ref="$3"
    local _installed_commit
    _installed_commit="$(installed_commit "$_plugin_id")"
    if [[ "$_installed_commit" != "$_git_ref" ]]; then
      "$HERDR_BIN" plugin install "$_source" --ref "$_git_ref" --yes
    fi
    printf '%s\n' "$_plugin_id" >>"$STATE_FILE"
    shift 3
  done
}

function main() {
  validate_arguments "$@"
  mkdir -p "$(dirname "$STATE_FILE")"
  set +x
  plugins_json="$("$HERDR_BIN" plugin list --json)"
  set -x
  uninstall_removed_plugins "$@"
  : >|"$STATE_FILE"
  install_plugins "$@"
}

main "$@"
