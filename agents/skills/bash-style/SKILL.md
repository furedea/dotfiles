---
name: bash-style
description: >
    User-specific conventions for designing, writing, and reviewing Bash scripts and bats tests.
---

# Shell Script Coding Style Guidelines

## File Header (every script)

Start executable Bash scripts with the following interpreter and error-handling defaults:

```sh
#!/usr/bin/env bash
set -euCo pipefail
```

- `#!/usr/bin/env bash` — resolve Bash from `PATH` and run with it explicitly, not with `sh`
- `set -euCo pipefail`:
    - `-e`: exit on error
    - `-u`: exit on undefined variable reference
    - `-C`: prohibit overwriting files with `>` (use `>|` to force)
    - `-o pipefail`: fail if any command in a pipe chain fails
- Choose the working directory by responsibility. Hooks that operate on a project must use the
  target project's working directory. Resolve bundled resources relative to the script's location.
  Use `cd "$(dirname "$0")"` only when all relative operations should use that location.
- `set -x` prints expanded commands to stderr before execution. Enable tracing only when useful
  for debugging; keep it disabled by default for scripts handling secrets or user input.

If tracing was explicitly enabled, suppress it around noisy or sensitive sections. Restore it only
when subsequent commands are safe to trace:

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

| Kind            | Convention                          | Example                 |
| --------------- | ----------------------------------- | ----------------------- |
| Constants       | `SCREAMING_SNAKE_CASE` + `readonly` | `readonly MAX_RETRY=3`  |
| Variables       | `snake_case`                        | `input_file="..."`      |
| Functions       | `snake_case`                        | `function parse_args()` |
| Local variables | `_snake_case` (leading underscore)  | `local _tmp_dir`        |
| Files           | `snake_case`                        | `lint_format.sh`        |
| Directories     | `kebab-case`                        | `claude-scripts/`       |

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

Indent with **2 spaces** (Google Shell Style Guide convention). Configure via `.editorconfig` at the project root; `shfmt` reads it automatically. Run `shfmt -i 2 -d <file>` to check. Common quoting errors are caught by `shellcheck`. The conventions above describe what those tools do not enforce.

## Task-Specific References

- When creating a new script and a complete skeleton is useful, read
  [script_template.md](references/script_template.md).
- When designing, writing, or reviewing bats tests, read
  [bats_testing.md](references/bats_testing.md) for layout, fixtures, assertions, and test commands.
  Shell scripts use bats for tests; available tools are bats, shellcheck, and shfmt.

Read only the reference relevant to the task.
