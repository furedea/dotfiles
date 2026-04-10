# Shell Script Coding Style Guidelines

## File Header (every script)

Every shell script must start with these three lines in order:

```sh
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
```

- `#!/bin/bash` — run with bash explicitly, not sh
- `set -euxCo pipefail`:
    - `-e`: exit on error
    - `-u`: exit on undefined variable reference
    - `-x`: print each command to stderr before execution (debug mode)
    - `-C`: prohibit overwriting files with `>` (use `>|` to force)
    - `-o pipefail`: fail if any command in a pipe chain fails
- `cd "$(dirname "$0")"` — change to the script's own directory so relative paths work regardless of where the caller invoked the script from

To suppress debug output for a section, bracket it:

```sh
set +x
# ... noisy or sensitive section ...
set -x
```

## usage Function

Every script must define a `usage` function that prints documentation to stderr and exits with failure. Use heredoc + redirect inside the function body:

```sh
function usage() {
    cat <<EOF >&2
Description:
    Description of this script.

Usage:
    $0 [OPTIONS] <FILE>

Options:
    --version, -v: print "$(basename "$0")" version
    --help, -h: print this
EOF
    exit 1
}
```

Call `usage` for `--help`/`-h` flags and for invalid argument combinations.

## Constants

Declare constants with `readonly`. Names use `SCREAMING_SNAKE_CASE`:

```sh
readonly INPUT_DIR="../data/input"
readonly MAX_RETRY=3
```

Always quote the right-hand side — values may contain spaces or special characters.

## Variables

- Quote all parameter expansions and string values to guard against word splitting and glob expansion (shellcheck SC2086 catches unquoted uses)
- Use default values for variables that may be empty or undefined:
    ```sh
    readonly OUTPUT="${1:-output.txt}"   # default value
    readonly NAME="${NAME:?NAME is required}"  # error if unset/empty
    ```
- Define variables just before first use (minimize lifetime)

## Naming

| Kind | Convention | Example |
|---|---|---|
| Constants | `SCREAMING_SNAKE_CASE` + `readonly` | `readonly MAX_RETRY=3` |
| Variables | `snake_case` | `input_file="..."` |
| Functions | `snake_case` | `function parse_args()` |
| Local variables | `_snake_case` (leading underscore) | `local _tmp_dir` |
| Files | `snake_case` | `lint_format.sh` |
| Directories | `kebab-case` | `claude-scripts/` |

Do not start names with a digit.

## Local Variables

Declare function-local variables with `local` and prefix with `_`:

```sh
function build_output() {
    local _src="$1"
    local _dst="$2"
    cp "$_src" "$_dst"
}
```

## Formatting

Formatting (indentation, spacing) is handled by `shfmt`. Common quoting errors are caught by `shellcheck`. The conventions above describe what those tools do not enforce.

## Full Template

```sh
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"

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

    set +x
    echo "processing: $_input"
    set -x

    # ... implementation ...
}

main "$@"
```
