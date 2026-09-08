# Testing with bats

Test shell scripts with [bats](https://github.com/bats-core/bats-core) (Bash Automated Testing System). Available tools: `bats`, `shellcheck`, `shfmt`.

### Directory Layout

```
tests/
├── <category>/
│   ├── test-helper/
│   │   └── setup.bash          # shared fixtures and helpers for this category
│   ├── feature_a.bats
│   └── feature_b.bats
└── <category>/
    ├── test-helper/
    │   └── setup.bash
    └── another.bats
```

- `test-helper/` is the project-standard directory name for helper libraries
- Each category gets its own `test-helper/` because helpers are domain-specific (hook input builders differ from CLI stubs)
- Test files: `.bats` extension, `snake_case` naming
- Helper files: `.bash` extension, loaded via `load test-helper/setup`

### File Structure

Every `.bats` file follows this order:

```bash
#!/usr/bin/env bats
# One-line description of what this file tests.

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/path/to/script_under_test.sh"
}

@test "descriptive lowercase sentence" {
  run bash "$SCRIPT" --help
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}
```

- Shebang: `#!/usr/bin/env bats` (not a Bash shebang)
- One comment line describing the file's scope
- `setup()` runs before each `@test` — wire fixtures and paths here, not assertions
- When a category has no shared helpers, derive `REPO_ROOT` inline:
    ```bash
    setup() {
      REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
    }
    ```

### Setup / Teardown Lifecycle

bats provides four lifecycle hooks, from broadest to narrowest scope:

| Hook                             | Scope            | Defined in                                        |
| -------------------------------- | ---------------- | ------------------------------------------------- |
| `setup_suite` / `teardown_suite` | Entire test run  | `setup_suite.bash` (auto-discovered at test root) |
| `setup_file` / `teardown_file`   | Per `.bats` file | The `.bats` file itself                           |
| `setup` / `teardown`             | Per `@test`      | The `.bats` file itself                           |

Use the narrowest scope that fits:

- `setup` — default choice; cheap per-test wiring (variable assignment, path setup)
- `setup_file` — expensive one-time setup shared across tests in a file (temp git repos, compiled fixtures)
- `setup_suite` — global preconditions (tool availability checks, environment validation)

```bash
setup_file() {
  load test-helper/setup
  create_temp_git_repo   # expensive — do once per file
  export TEMP_REPO       # export so tests see it
}

teardown_file() {
  rm -rf "$TEMP_REPO"
}

setup() {
  load test-helper/setup
  HOOK="$HOOK_DIR/my_hook.sh"
}
```

Variables set in `setup_file` must be `export`ed to be visible in `setup` and `@test` blocks (they run in subshells).

### Test Naming

Use `@test "descriptive lowercase sentence"` — describe the observable behavior, not the implementation:

```bash
@test "allows push to feature branch" { ... }
@test "blocks --force" { ... }
@test "exits 0 when no file_path in input" { ... }
```

### Section Separators

Group related tests with comment banners:

```bash
# ============================================================
# Allowed: normal pushes
# ============================================================
```

### Assertions

Use raw bats built-ins (`run`, `$status`, `$output`, `${lines[@]}`):

```bash
run bash "$SCRIPT" "$arg"
[ "$status" -eq 0 ]                    # exit status
[[ "$output" == *"expected text"* ]]   # output substring
[ "${lines[0]}" = "first line" ]       # exact line
[ "${#lines[@]}" -eq 3 ]              # line count
! [[ "$output" == *"unexpected"* ]]    # negation
```

Always use `run` before checking `$status` or `$output` — without it, a non-zero exit aborts the test (bats enables `set -e` inside `@test` blocks).

When a command is expected to succeed and you only care about side effects (a file was created, a variable was set), omit `run` — bats' `set -e` will fail the test automatically if the command errors.

### Loop-Based Assertions

When checking multiple items in a loop, report which item failed:

```bash
@test "all scripts pass syntax check" {
  for script in "${SCRIPTS[@]}"; do
    bash -n "$script" || {
      echo "Syntax error in: $script"
      return 1
    }
  done
}
```

### Helper Functions (test-helper/setup.bash)

Put shared fixtures in `test-helper/setup.bash`. Common patterns:

```bash
REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
HOOK_DIR="$REPO_ROOT/agents/hooks"

make_input() {
  jq -n --arg cmd "$1" '{"tool_input":{"command":$cmd}}'
}

create_temp_git_repo() {
  TEMP_REPO="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/repo.XXXXXX")"
  git -C "$TEMP_REPO" init --quiet
  git -C "$TEMP_REPO" config user.email "test@test.com"
  git -C "$TEMP_REPO" config user.name "Test"
  git -C "$TEMP_REPO" config commit.gpgsign false
  touch "$TEMP_REPO/.gitkeep"
  git -C "$TEMP_REPO" add .gitkeep
  git -C "$TEMP_REPO" commit --quiet -m "initial"
}
```

- Use `jq` for JSON construction (proper escaping)
- Build helpers that mirror the input format of the code under test
- For external command stubs (e.g. `gh`), create an executable script in `$BATS_TEST_TMPDIR/bin/` and prepend it to `$PATH`

### Temporary Directories

bats provides auto-cleaned temp directories at three scopes:

| Variable            | Scope                 | Cleaned after |
| ------------------- | --------------------- | ------------- |
| `BATS_TEST_TMPDIR`  | Per `@test`           | Each test     |
| `BATS_FILE_TMPDIR`  | Per `.bats` file      | Each file     |
| `BATS_SUITE_TMPDIR` | Per `bats` invocation | Entire run    |

Use the narrowest scope that fits. Prefer these over raw `mktemp` — bats handles cleanup.

### Making Scripts Testable

To source individual functions from a script without executing `main`, guard the entry point:

```bash
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
```

This lets tests `source` the script and call functions in isolation.

### Running Tests

```bash
bats tests/                        # all tests
bats tests/agents/hooks/claude/           # one category
bats tests/agents/hooks/claude/guard_dangerous_git.bats  # one file
bats --filter "blocks" tests/      # only tests matching pattern
bats --negative-filter "slow" tests/  # exclude tests matching pattern
```

### Test Organization Rules

- One `.bats` file per script or module under test
- Test allowed/passing cases first, then blocked/failing cases
- Each `@test` tests one behavior. Split independently changing outcomes, not multiple assertions
  that observe the same behavior.
- Keep test bodies short; move complex setup into helper functions
