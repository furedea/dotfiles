#!/usr/bin/env bats
# Executable shell entry points delegate quality behavior to the shared Python runtime.

setup() {
  load test-helper/setup
  LINT_HOOKS=(
    "$HOOK_DIR/lint_format_gha.sh"
    "$HOOK_DIR/lint_format_js.sh"
    "$HOOK_DIR/lint_format_json_toml.sh"
    "$HOOK_DIR/lint_format_lua.sh"
    "$HOOK_DIR/lint_format_md.sh"
    "$HOOK_DIR/lint_format_nix.sh"
    "$HOOK_DIR/lint_format_py.sh"
    "$HOOK_DIR/lint_format_rs.sh"
    "$HOOK_DIR/lint_format_sh.sh"
    "$HOOK_DIR/lint_format_tex.sh"
    "$HOOK_DIR/lint_format_txt.sh"
  )
}

@test "all lint_format hooks exist" {
  for hook in "${LINT_HOOKS[@]}"; do
    [ -f "$hook" ] || {
      echo "Missing: $hook"
      return 1
    }
  done
}

@test "all lint_format hooks are executable" {
  for hook in "${LINT_HOOKS[@]}"; do
    [ -x "$hook" ] || {
      echo "Not executable: $hook"
      return 1
    }
  done
}

@test "all lint_format hooks pass bash syntax check" {
  for hook in "${LINT_HOOKS[@]}"; do
    bash -n "$hook" || {
      echo "Syntax error in: $hook"
      return 1
    }
  done
}

@test "all lint_format hooks have set -e" {
  for hook in "${LINT_HOOKS[@]}"; do
    grep -q 'set -e' "$hook" || {
      echo "Missing set -e: $hook"
      return 1
    }
  done
}

@test "all lint_format hooks resolve bash from PATH" {
  for hook in "${LINT_HOOKS[@]}"; do
    head -1 "$hook" | grep -q '#!/usr/bin/env bash' || {
      echo "Missing bash shebang: $hook"
      return 1
    }
  done
}

@test "lint_format_py exits 0 when no file_path in input" {
  run bash "$HOOK_DIR/lint_format_py.sh" <<< '{"tool_input":{}}'
  [ "$status" -eq 0 ]
}

@test "lint_format_sh exits 0 when no file_path in input" {
  run bash "$HOOK_DIR/lint_format_sh.sh" <<< '{"tool_input":{}}'
  [ "$status" -eq 0 ]
}

@test "lint_format_js exits 0 when no file_path in input" {
  run bash "$HOOK_DIR/lint_format_js.sh" <<< '{"tool_input":{}}'
  [ "$status" -eq 0 ]
}

@test "lint_format_json_toml exits 0 when no file_path in input" {
  run bash "$HOOK_DIR/lint_format_json_toml.sh" <<< '{"tool_input":{}}'
  [ "$status" -eq 0 ]
}

@test "lint_format_gha exits 0 when no file_path in input" {
  run bash "$HOOK_DIR/lint_format_gha.sh" <<< '{"tool_input":{}}'
  [ "$status" -eq 0 ]
}
