#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"

GITHUB_DIR="$(pwd)"
readonly GITHUB_DIR
readonly SETUP_REPO="$GITHUB_DIR/setup_repo.sh"

function usage() {
  cat <<EOF >&2
Description:
    Create a GitHub repository, clone it into the ghq root, apply template
    renames, and apply standard repository settings.

Usage:
    $0 <name> [gh repo create flags...]

Arguments:
    <name>: 'foo' for the authenticated user or 'owner/foo' for explicit owner.

Examples:
    $0 agent-harness --private --template furedea/template-rust

Options:
    --help, -h: print this

Notes:
    Do not pass --clone. This script controls the local clone destination.
    The clone destination is printed to stdout on success.
EOF
  exit 1
}

function main() {
  [[ $# -eq 0 ]] && usage

  local _name="$1"
  shift

  [[ "$_name" == "-h" || "$_name" == "--help" ]] && usage

  local _short="${_name##*/}"
  local _full _owner _dest _has_template=false _arg

  if [[ "$_name" == */* ]]; then
    _full="$_name"
  else
    _owner=$(gh api user --jq .login)
    _full="$_owner/$_short"
  fi

  for _arg in "$@"; do
    if [[ "$_arg" == "--clone" ]]; then
      echo "create_repo.sh: do not pass --clone; create_repo.sh controls the clone destination" >&2
      return 1
    fi
    if [[ "$_arg" == "--template" || "$_arg" == --template=* ]]; then
      _has_template=true
    fi
  done

  _dest="$(ghq root)/github.com/$_full"
  if [[ -e "$_dest" ]]; then
    echo "create_repo.sh: local destination already exists: $_dest" >&2
    return 1
  fi

  echo "→ creating GitHub repo: $_full" >&2
  gh repo create "$_name" "$@" >&2

  if [[ "$_has_template" == true ]]; then
    echo "→ waiting for template repository to become cloneable: $_full" >&2
    wait_for_default_branch "$_full"
  fi

  echo "→ cloning into $_dest" >&2
  mkdir -p "$(dirname "$_dest")"
  gh repo clone "$_full" "$_dest" >&2

  apply_template "$_dest" "$_short"

  "$SETUP_REPO" "$_full" >&2
  if [[ -f "$_dest/lefthook.yml" ]] && command -v lefthook >/dev/null; then
    (cd "$_dest" && lefthook install) >&2
  fi

  printf '%s\n' "$_dest"
}

function wait_for_default_branch() {
  local _repo="$1"
  local _branch _ref _attempt

  for _attempt in {1..30}; do
    _branch=$(gh api "repos/$_repo" --jq '.default_branch // empty' 2>/dev/null || true)
    if [[ -n "$_branch" ]]; then
      _ref=$(gh api "repos/$_repo/git/ref/heads/$_branch" --jq '.ref // empty' 2>/dev/null || true)
      [[ "$_ref" == "refs/heads/$_branch" ]] && return 0
    fi
    sleep 2
  done

  echo "create_repo.sh: remote default branch is not ready: $_repo" >&2
  return 1
}

function apply_template() {
  local _dest="$1"
  local _name="$2"
  local _file _tmp

  for _file in pyproject.toml Cargo.toml; do
    if [[ -f "$_dest/$_file" ]]; then
      perl -0pi -e "s/^name = \"template-[a-z]*\"/name = \"$_name\"/m" "$_dest/$_file"
    fi
  done

  if [[ -f "$_dest/package.json" ]] && command -v jq >/dev/null; then
    _tmp=$(mktemp)
    jq --arg n "$_name" '.name = $n' "$_dest/package.json" >|"$_tmp"
    mv "$_tmp" "$_dest/package.json"
  fi
}

main "$@"
