# Bash Script Template

```sh
#!/usr/bin/env bash
set -euCo pipefail
# Resolve the working directory according to the task; see the parent skill.

function usage() {
  cat <<EOF >&2
Description:
    Does X given Y.

Usage:
    $0 [OPTIONS] <INPUT>

Options:
    --dry-run: print actions without executing
    --help, -h: print this
EOF
  exit 1
}

readonly LOG_DIR="../logs"

function main() {
  local _input="${1:?$(usage)}"

  echo "processing: $_input"

  # ... implementation ...
}

main "$@"
```
