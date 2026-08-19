#!/bin/bash
set -euCo pipefail
cd "$(dirname "$0")"

function usage() {
  cat <<EOF >&2
Description:
    Clone or fast-forward all repositories owned by the authenticated GitHub user.

Usage:
    repo sync [--dry-run]

Options:
    --dry-run: print planned operations without changing repositories
    --help, -h: print this
EOF
  exit 1
}

function sync_repository() {
  local _repository="$1"
  local _target="$2"
  local _is_dry_run="$3"

  if [[ ! -e "$_target" ]]; then
    printf '[clone] %s -> %s\n' "$_repository" "$_target"
    [[ "$_is_dry_run" == "true" ]] || gh repo clone "$_repository" "$_target"
    return
  fi

  if [[ ! -e "$_target/.git" ]]; then
    printf 'Not a Git repository: %s\n' "$_target" >&2
    return 1
  fi

  printf '[pull] %s\n' "$_target"
  [[ "$_is_dry_run" == "true" ]] || git -C "$_target" pull --ff-only
}

function main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
  fi
  local _is_dry_run=false
  if [[ "${1:-}" == "--dry-run" ]]; then
    _is_dry_run=true
    shift
  fi
  [[ "$#" -eq 0 ]] || usage

  local _owner
  _owner="$(gh api user --jq .login)"
  local _owner_dir
  _owner_dir="$(ghq root)/github.com/$_owner"
  local _repositories
  _repositories="$(
    gh repo list "$_owner" \
      --limit 10000 \
      --json nameWithOwner \
      --jq '.[].nameWithOwner'
  )"

  [[ "$_is_dry_run" == "true" ]] || mkdir -p "$_owner_dir"

  local _clone_count=0
  local _pull_count=0
  local _failure_count=0
  local _repository
  while IFS= read -r _repository; do
    [[ -n "$_repository" ]] || continue
    local _target="$_owner_dir/${_repository#*/}"
    local _operation="pull"
    [[ -e "$_target" ]] || _operation="clone"
    if ! sync_repository "$_repository" "$_target" "$_is_dry_run"; then
      _failure_count=$((_failure_count + 1))
    elif [[ "$_operation" == "clone" ]]; then
      _clone_count=$((_clone_count + 1))
    else
      _pull_count=$((_pull_count + 1))
    fi
  done <<<"$_repositories"

  printf '[summary] cloned=%d pulled=%d failed=%d\n' \
    "$_clone_count" "$_pull_count" "$_failure_count"
  [[ "$_failure_count" -eq 0 ]]
}

main "$@"
