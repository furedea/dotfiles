#!/bin/bash
set -euCo pipefail
cd "$(dirname "$0")"
GITHUB_DIR="$(pwd)"
readonly GITHUB_DIR
source "$GITHUB_DIR/repository.bash"

function usage() {
  cat <<EOF >&2
Description:
    Apply standard repository settings and ruleset to a GitHub repository.
    Idempotent: existing ruleset with the same name is updated in place.

Usage:
    repo configure <name-or-owner/name>

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

function enable_vulnerability_alerts() {
  local _repo="$1"
  gh api "repos/$_repo/vulnerability-alerts" -X PUT >/dev/null
  echo "Enabled vulnerability alerts and dependency graph on $_repo"
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
  [[ $# -ne 1 ]] && usage
  [[ "$1" == -* ]] && usage

  local _repo="$1"
  _repo=$(resolve_repository "$_repo")

  apply_settings "$_repo"
  enable_vulnerability_alerts "$_repo"
  apply_ruleset "$_repo"
}

main "$@"
