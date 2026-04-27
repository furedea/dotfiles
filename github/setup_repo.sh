#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
GITHUB_DIR="$(pwd)"
readonly GITHUB_DIR

function usage() {
  cat <<EOF >&2
Description:
    Apply standard repository settings and ruleset to a GitHub repository.
    Idempotent: existing ruleset with the same name is updated in place.

Usage:
    $0 <owner/repo>

Options:
    --help, -h: print this
EOF
  exit 1
}

function apply_settings() {
  local _repo="$1"
  gh api "repos/$_repo" -X PATCH --input "$GITHUB_DIR/repo_settings.json" >/dev/null
  echo "Applied repo settings to $_repo"
}

function apply_ruleset() {
  local _repo="$1"
  local _name _id
  _name=$(jq -r .name "$GITHUB_DIR/ruleset.json")
  _id=$(gh api "repos/$_repo/rulesets" --jq ".[] | select(.name == \"$_name\") | .id")
  if [[ -n "$_id" ]]; then
    gh api "repos/$_repo/rulesets/$_id" -X PUT --input "$GITHUB_DIR/ruleset.json" >/dev/null
    echo "Updated ruleset $_id on $_repo"
  else
    gh api "repos/$_repo/rulesets" -X POST --input "$GITHUB_DIR/ruleset.json" >/dev/null
    echo "Created ruleset on $_repo"
  fi
}

function main() {
  local _repo=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h | --help) usage ;;
      *)
        _repo="$1"
        shift
        ;;
    esac
  done

  [[ -z "$_repo" ]] && usage

  apply_settings "$_repo"
  apply_ruleset "$_repo"
}

main "$@"
