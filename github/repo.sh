#!/bin/bash
set -euCo pipefail
cd "$(dirname "$0")"

REPO_DIR="$(pwd)"
readonly REPO_DIR
readonly CREATE_REPO="$REPO_DIR/create_repo.sh"
readonly CONFIGURE_REPO="$REPO_DIR/configure_repo.sh"
readonly SYNC_REPOS="$REPO_DIR/sync_repos.sh"

function usage() {
  cat <<EOF >&2
Description:
    Manage repositories with the standard GitHub workflow.

Usage:
    repo <command> [arguments]

Commands:
    create       Create, clone, and configure a repository.
    configure    Apply standard settings and rulesets.
    sync         Clone or fast-forward all owned repositories.

Options:
    --help, -h: print this

Run "repo <command> --help" for command-specific options.
EOF
  exit 1
}

function main() {
  local _command="${1:-}"

  case "$_command" in
    create)
      shift
      exec "$CREATE_REPO" "$@"
      ;;
    configure)
      shift
      exec "$CONFIGURE_REPO" "$@"
      ;;
    sync)
      shift
      exec "$SYNC_REPOS" "$@"
      ;;
    -h | --help | "") usage ;;
    *) usage ;;
  esac
}

main "$@"
