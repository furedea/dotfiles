#!/bin/bash
set -euCo pipefail
cd "$(dirname "$0")"

GITHUB_DIR="$(pwd)"
readonly GITHUB_DIR
readonly CONFIGURE_REPO="$GITHUB_DIR/configure_repo.sh"
source "$GITHUB_DIR/repository.bash"

function usage() {
  cat <<EOF >&2
Description:
    Create a GitHub repository, clone it into the ghq root, apply template
    renames, and apply standard repository settings.

Usage:
    repo create <name-or-owner/name> <visibility> [options]

Arguments:
    <name-or-owner/name>: 'foo' for the authenticated user or 'owner/foo'.

Examples:
    repo create agent-harness --private --template furedea/template-rust

Visibility:
    --public, --private, --internal: set exactly one repository visibility

Common options:
    --template, -p <repository>: create from a template repository
    --include-all-branches: include every branch from the template
    --description, -d <text>: set the repository description
    --homepage <url>: set the repository homepage
    --add-readme: add a README
    --gitignore, -g <template>: add a .gitignore template
    --license, -l <keyword>: add a license
    --disable-issues: disable issues
    --disable-wiki: disable the wiki
    --team, -t <name>: grant access to an organization team
    --help, -h: print this

Notes:
    --clone/-c, --source/-s, --push, and --remote/-r are not supported because
    this command controls the local clone destination.
    Other compatible gh repo create options are forwarded.
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
  local _full _dest _has_template=false _arg _visibility_count=0

  _full=$(resolve_repository "$_name")

  for _arg in "$@"; do
    if is_unsupported_create_option "$_arg"; then
      echo "repo create: $_arg is not supported; repo create controls the local clone destination" >&2
      return 1
    fi

    case "$_arg" in
      -h | --help) usage ;;
      --template | --template=* | -p) _has_template=true ;;
      --public | --private | --internal) _visibility_count=$((_visibility_count + 1)) ;;
    esac
  done

  if [[ "$_visibility_count" -ne 1 ]]; then
    echo "repo create: exactly one of --public, --private, or --internal is required" >&2
    return 1
  fi

  _dest="$(ghq root)/github.com/$_full"
  if [[ -e "$_dest" ]]; then
    echo "repo create: local destination already exists: $_dest" >&2
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

  "$CONFIGURE_REPO" "$_full" >&2
  if [[ -f "$_dest/lefthook.yml" ]] && command -v lefthook >/dev/null; then
    (cd "$_dest" && lefthook install) >&2
  fi

  printf '%s\n' "$_dest"
}

function is_unsupported_create_option() {
  case "$1" in
    --clone | --clone=* | -c | --push | --push=*) return 0 ;;
    --source | --source=* | -s | -s=* | --remote | --remote=* | -r | -r=*) return 0 ;;
    *) return 1 ;;
  esac
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

  echo "repo create: remote default branch is not ready: $_repo" >&2
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
