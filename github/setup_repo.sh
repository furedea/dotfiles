#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"

function usage() {
  cat <<EOF >&2
Description:
    Apply standard repository settings and rulesets to a GitHub repository.
    If <owner/repo> is omitted, detects from the current directory via gh repo view.

Usage:
    $0 [OPTIONS] [<owner/repo>]

Options:
    -t, --template <name>: apply language-specific ruleset (python|typescript|rust|tex)
    --help, -h: print this
EOF
  exit 1
}

GITHUB_DIR="$(pwd)"
readonly GITHUB_DIR

function detect_repo() {
  gh repo view --json nameWithOwner -q .nameWithOwner
}

function apply_settings() {
  local _repo="$1"
  gh api "repos/$_repo" -X PATCH --input "$GITHUB_DIR/repo_settings.json" >/dev/null
  echo "Applied repo settings to $_repo"
}

function apply_base_ruleset() {
  local _repo="$1"
  gh api "repos/$_repo/rulesets" -X POST --input "$GITHUB_DIR/ruleset_base.json" >/dev/null
  echo "Applied base ruleset to $_repo"
}

function apply_lang_ruleset() {
  local _repo="$1"
  local _lang="$2"
  local _ruleset_file="$GITHUB_DIR/ruleset_${_lang}.json"
  if [[ ! -f "$_ruleset_file" ]]; then
    echo "Unknown language: $_lang" >&2
    return 1
  fi
  gh api "repos/$_repo/rulesets" -X POST --input "$_ruleset_file" >/dev/null
  echo "Applied $_lang ruleset to $_repo"
}

function main() {
  local _repo=""
  local _template=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
    -t | --template)
      _template="$2"
      shift 2
      ;;
    -h | --help) usage ;;
    *)
      _repo="$1"
      shift
      ;;
    esac
  done

  if [[ -z "$_repo" ]]; then
    _repo=$(detect_repo)
  fi

  apply_settings "$_repo"
  apply_base_ruleset "$_repo"

  if [[ -n "$_template" ]]; then
    apply_lang_ruleset "$_repo" "$_template"
  fi
}

main "$@"
