#!/usr/bin/env bats
# Behavioral tests for lint_format_rs.sh under the Quality Loop model:
# format only (rustfmt). Cargo clippy is cross-file and lives at pre-commit / CI.

setup() {
  load test-helper/setup
  HOOK="$HOOK_DIR/lint_format_rs.sh"
  TEST_TMPDIR="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/lintrs.XXXXXX")"
}

teardown() {
  [ -d "${TEST_TMPDIR:-}" ] && rm -rf "$TEST_TMPDIR"
}

@test "lint_format_rs does not invoke cargo clippy" {
  ! grep -q 'cargo[[:space:]]\+clippy' "$HOOK"
}

@test "lint_format_rs auto-formats a malformatted file" {
  if ! command -v rustfmt >/dev/null 2>&1; then
    skip "rustfmt not installed"
  fi
  local _file="$TEST_TMPDIR/badfmt.rs"
  printf 'fn main(){let x=1;println!("{}",x);}\n' > "$_file"
  run bash "$HOOK" <<< "$(make_post_tool_input "$_file")"
  [ "$status" -eq 0 ]
  grep -q '^fn main()' "$_file"
}

@test "lint_format_rs exits 0 when input has no file_path" {
  run bash "$HOOK" <<< '{"tool_input":{}}'
  [ "$status" -eq 0 ]
}

@test "lint_format_rs reports formatter failure without blocking the edit" {
  mkdir -p "$TEST_TMPDIR/bin"
  printf '#!/usr/bin/env bash\necho "cannot parse source" >&2\nexit 1\n' > "$TEST_TMPDIR/bin/rustfmt"
  chmod +x "$TEST_TMPDIR/bin/rustfmt"
  touch "$TEST_TMPDIR/source.rs"
  export PATH="$TEST_TMPDIR/bin:$PATH"

  run bash "$HOOK" <<< "$(make_post_tool_input "$TEST_TMPDIR/source.rs")"

  [ "$status" -eq 0 ]
  local _context
  _context=$(jq -r '.hookSpecificOutput.additionalContext' <<< "$output")
  [[ "$_context" == *"failed"* ]]
  [[ "$_context" == *"source.rs"* ]]
  [[ "$_context" == *"cannot parse source"* ]]
}
