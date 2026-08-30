#!/usr/bin/env bash
set -euxCo pipefail
cd "$(dirname "$0")"

function usage() {
  cat <<EOF >&2
Description:
    Confirm and immediately squash-merge the pull request for a repository.

Usage:
    $0 <REPOSITORY_DIRECTORY>

Options:
    --help, -h: print this
EOF
  exit 1
}

readonly GH_BIN="${GH_BIN:-gh}"
readonly GIT_BIN="${GIT_BIN:-git}"

function branch_is_checked_out() {
  local _branch="$1"
  local _worktrees="$2"
  local _line

  while IFS= read -r _line; do
    if [[ "$_line" == "branch refs/heads/${_branch}" ]]; then
      return 0
    fi
  done <<<"$_worktrees"

  return 1
}

function confirm_merge() {
  local _answer
  if ! IFS= read -rsn 1 _answer; then
    printf '\nCancelled.\n'
    return 1
  fi

  case "$_answer" in
    "" | $'\r')
      return 0
      ;;
    $'\e' | $'\003')
      printf '\nCancelled.\n'
      return 1
      ;;
    *)
      printf '\nCancelled.\n'
      wait_for_close
      return 1
      ;;
  esac
}

function wait_for_close() {
  local _answer

  printf '\nPress Enter or Esc to close...'
  while true; do
    if ! IFS= read -rsn 1 _answer; then
      return 0
    fi

    case "$_answer" in
      "" | $'\r' | $'\e' | $'\003')
        printf '\n'
        return 0
        ;;
    esac
  done
}

function wait_on_failure() {
  local _status="$1"

  if [[ "$_status" -ne 0 ]]; then
    wait_for_close
  fi
}

function main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || "$#" -ne 1 ]]; then
    usage
  fi

  trap 'wait_on_failure "$?"' EXIT
  trap 'printf "\nCancelled.\n"; exit 0' INT

  local _repository_directory="$1"
  local _repository_root
  _repository_root="$("$GIT_BIN" -C "$_repository_directory" rev-parse --show-toplevel)"
  cd "$_repository_root"

  local _working_tree_status
  _working_tree_status="$("$GIT_BIN" -C "$_repository_root" status --porcelain=v1)"
  if [[ -n "$_working_tree_status" ]]; then
    printf 'Cannot merge: working tree has uncommitted changes.\n'
    return 1
  fi

  local _pr_fields
  _pr_fields="$(
    "$GH_BIN" pr view \
      --json number,title,baseRefName,headRefName \
      --jq '[.number, .title, .baseRefName, .headRefName] | @tsv'
  )"

  local _pr_number
  local _pr_title
  local _base_ref
  local _head_ref
  IFS=$'\t' read -r _pr_number _pr_title _base_ref _head_ref <<<"$_pr_fields"

  local _head_commit
  _head_commit="$("$GIT_BIN" -C "$_repository_root" rev-parse HEAD)"

  local _worktrees
  _worktrees="$("$GIT_BIN" -C "$_repository_root" worktree list --porcelain)"

  local -a _merge_command=(
    "$GH_BIN"
    pr
    merge
    --squash
  )
  local _cleanup_message
  if branch_is_checked_out "$_base_ref" "$_worktrees"; then
    _cleanup_message="Local cleanup: keep this worktree and local branch; ${_base_ref} is checked out elsewhere."
  else
    _merge_command+=(--delete-branch)
    _cleanup_message="Local cleanup: delete the merged branch and switch to ${_base_ref}."
  fi
  _merge_command+=(--match-head-commit "$_head_commit")

  printf 'PR #%s: %s\n%s -> %s\n\n' \
    "$_pr_number" \
    "$_pr_title" \
    "$_head_ref" \
    "$_base_ref"
  printf '%s\n\n' "$_cleanup_message"
  printf 'Enter / Ctrl+M  Squash and merge now\nEsc             Cancel\n'

  if ! confirm_merge; then
    return 0
  fi

  printf '\n'
  "${_merge_command[@]}"
}

main "$@"
