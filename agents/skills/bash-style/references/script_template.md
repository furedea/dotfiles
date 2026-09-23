# Bash Script Template

```sh
#!/usr/bin/env bash
set -euCo pipefail
# Resolve the working directory according to the task; see the parent skill.

function usage() {
  cat <<EOF
Description:
    Does X given Y.

Usage:
    $0 [OPTIONS] <INPUT>

Options:
    --dry-run: print actions without executing
    --help, -h: print this
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly LOG_DIR="$SCRIPT_DIR/../logs"

function main() {
  case "${1:-}" in
    --help | -h)
      usage
      exit 0
      ;;
    "")
      usage >&2
      exit 1
      ;;
  esac
  local _input="$1"

  echo "processing: $_input"

  # ... implementation ...
}

main "$@"
```
