#!/usr/bin/env bats
# Codex diagnostics come directly from shared Python quality checks.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../.." && pwd)"
  HOOK="$REPO_ROOT/agents/codex/hooks/adapters.py"
  mkdir -p "$BATS_TEST_TMPDIR/bin"
  printf 'x = 1\n' >"$BATS_TEST_TMPDIR/x.py"
  cat >"$BATS_TEST_TMPDIR/bin/ruff" <<'STUB'
#!/usr/bin/env bash
if [[ "$*" == *--output-format=concise* && "${LINT_FIXTURE_FAIL:-0}" == 1 ]]; then
  echo 'ruff: F821 undefined name'
  exit 1
fi
echo 'environment noise' >&2
STUB
  chmod +x "$BATS_TEST_TMPDIR/bin/ruff"
  export PATH="$BATS_TEST_TMPDIR/bin:$PATH"
  INPUT="$(jq -n --arg cwd "$BATS_TEST_TMPDIR" '{cwd:$cwd,tool_input:{command:"*** Update File: x.py"}}')"
}

@test "lint adapter prints usage for invalid arguments" {
  run python3 -I -B "$HOOK" lint --help
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "relative patch path produces plain-text quality diagnostics" {
  run env LINT_FIXTURE_FAIL=1 python3 -I -B "$HOOK" lint <<<"$INPUT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ruff: F821 undefined name"* ]]
  [[ "$output" == *"$BATS_TEST_TMPDIR/x.py"* ]]
  [[ "$output" != *"hookSpecificOutput"* ]]
}

@test "successful tools emit neither stdout nor stderr noise" {
  run --separate-stderr python3 -I -B "$HOOK" lint <<<"$INPUT"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}
