#!/usr/bin/env bats
# Tests for codex/hooks/adapt_lint_format.sh
# Focuses on patch_paths extraction and hook_for_path dispatch logic.

setup_file() {
  bats_require_minimum_version 1.5.0
}

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../.." && pwd)"
  HOOK="$REPO_ROOT/agents/codex/hooks/adapt_lint_format.sh"
}

run_adapter() {
  local _home="$1"
  local _input="$2"

  env -i HOME="$_home" PATH="$PATH" "$HOOK" <<<"$_input"
}

dump_run_diagnostic() {
  local _label="$1"

  {
    printf 'diagnostic: %s\n' "$_label"
    printf 'status: %s\n' "$status"
    printf 'stdout:\n%s\n' "${output:-}"
    printf 'stderr:\n%s\n' "${stderr:-}"
  } >&3
}

@test "prints usage with --help" {
  run "$HOOK" --help
  [ "$status" -ne 0 ]
  [[ "$output" == *"Usage"* ]]
}

# ============================================================
# JSON additionalContext translation (Claude format -> Codex plain text)
# ============================================================

@test "adapter extracts additionalContext from hook JSON output" {
  local _tmp
  _tmp="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/codex.XXXXXX")"
  local _file="$_tmp/x.py"
  printf 'x = 1\n' >"$_file"

  # Stub hook directory: replace lint_format_py.sh with one that emits Claude-format JSON.
  local _stub_dir="$_tmp/hooks"
  mkdir -p "$_stub_dir"
  cat >"$_stub_dir/lint_format_py.sh" <<EOF
#!/bin/bash
jq -cn '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:"ruff: F821 undefined name"}}'
EOF
  chmod +x "$_stub_dir/lint_format_py.sh"

  # Patch input describing a change to x.py
  local _input
  _input=$(jq -n --arg cwd "$_tmp" --arg cmd "*** Update File: x.py" \
    '{cwd:$cwd, tool_input:{command:$cmd}}')

  mkdir -p "$_tmp/.claude/hooks"
  cp "$_stub_dir/lint_format_py.sh" "$_tmp/.claude/hooks/"

  run run_adapter "$_tmp" "$_input"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ruff: F821 undefined name"* ]]
  [[ "$output" != *"hookSpecificOutput"* ]]
}

@test "adapter passes through non-JSON hook output unchanged" {
  local _tmp
  _tmp="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/codex.XXXXXX")"
  local _file="$_tmp/x.sh"
  printf '#!/bin/bash\necho hi\n' >"$_file"

  local _stub_dir="$_tmp/.claude/hooks"
  mkdir -p "$_stub_dir"
  cat >"$_stub_dir/lint_format_sh.sh" <<'EOF'
#!/bin/bash
echo "plain-text hook output: SC2086 quote me"
EOF
  chmod +x "$_stub_dir/lint_format_sh.sh"

  local _input
  _input=$(jq -n --arg cwd "$_tmp" --arg cmd "*** Update File: x.sh" \
    '{cwd:$cwd, tool_input:{command:$cmd}}')

  run run_adapter "$_tmp" "$_input"
  [ "$status" -eq 0 ]
  [[ "$output" == *"plain-text hook output"* ]]
}

@test "adapter resolves lint hooks from the harness root" {
  local _home
  _home="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/home.XXXXXX")"
  local _harness_root
  _harness_root="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/harness.XXXXXX")"
  local _file="$_home/x.sh"
  printf '#!/usr/bin/env bash\necho hi\n' >"$_file"

  mkdir -p "$_harness_root/.claude/hooks"
  cat >"$_harness_root/.claude/hooks/lint_format_sh.sh" <<'STUB'
#!/usr/bin/env bash
set -euxCo pipefail
cd "$(dirname "$0")"

echo "harness-root hook"
STUB
  chmod +x "$_harness_root/.claude/hooks/lint_format_sh.sh"

  local _input
  _input=$(jq -n --arg cwd "$_home" --arg cmd "*** Update File: x.sh" \
    '{cwd:$cwd, tool_input:{command:$cmd}}')

  run env -i HOME="$_home" AGENT_HARNESS_ROOT="$_harness_root" PATH="$PATH" \
    "$HOOK" <<<"$_input"

  [ "$status" -eq 0 ]
  [[ "$output" == *"harness-root hook"* ]]
}

@test "adapter emits no stdout when hook is silent (clean lint)" {
  local _tmp
  _tmp="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/codex.XXXXXX")"
  local _file="$_tmp/x.py"
  printf 'x = 1\n' >"$_file"

  local _stub_dir="$_tmp/.claude/hooks"
  mkdir -p "$_stub_dir"
  cat >"$_stub_dir/lint_format_py.sh" <<'EOF'
#!/bin/bash
# Clean: emit nothing
EOF
  chmod +x "$_stub_dir/lint_format_py.sh"

  local _input
  _input=$(jq -n --arg cwd "$_tmp" --arg cmd "*** Update File: x.py" \
    '{cwd:$cwd, tool_input:{command:$cmd}}')

  run --separate-stderr run_adapter "$_tmp" "$_input"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "adapter ignores stderr from a successful lint hook" {
  local _tmp
  _tmp="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/codex.XXXXXX")"
  local _file="$_tmp/x.py"
  printf 'x = 1\n' >"$_file"

  local _stub_dir="$_tmp/.claude/hooks"
  mkdir -p "$_stub_dir"
  cat >"$_stub_dir/lint_format_py.sh" <<'EOF'
#!/bin/bash
echo "environment noise" >&2
EOF
  chmod +x "$_stub_dir/lint_format_py.sh"

  local _input
  _input=$(jq -n --arg cwd "$_tmp" --arg cmd "*** Update File: x.py" \
    '{cwd:$cwd, tool_input:{command:$cmd}}')

  run --separate-stderr run_adapter "$_tmp" "$_input"
  if [ "$status" -ne 0 ] || [ -n "$output" ] || [[ "$stderr" == *"environment noise"* ]]; then
    dump_run_diagnostic "adapter ignores stderr from a successful lint hook"
  fi
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [[ "$stderr" != *"environment noise"* ]]
}
