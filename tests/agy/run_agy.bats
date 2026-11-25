#!/usr/bin/env bats
# Executable specifications for the agy wrapper that disables telemetry where agy accepts the flag.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/scripts/agy/run_agy.sh"
  AGY_STUB="$BATS_TEST_TMPDIR/agy"
  create_agy_stub
}

run_wrapper() {
  run --separate-stderr env AGY_BIN="$AGY_STUB" /bin/bash "$SCRIPT" "$@"
}

assert_passed_through() {
  run_wrapper "$@"

  [ "$status" -eq 0 ]
  [ "$output" = "$(if (($# > 0)); then printf '%s\n' "$@"; fi)" ]
}

@test "acp receives --disable_telemetry right after the subcommand" {
  run_wrapper acp --gemini-dir /tmp/profile --app-data-dir antigravity-acp

  [ "$status" -eq 0 ]
  [ "$output" = "$(printf '%s\n' acp --disable_telemetry --gemini-dir /tmp/profile --app-data-dir antigravity-acp)" ]
}

@test "acp without further arguments still disables telemetry" {
  run_wrapper acp

  [ "$status" -eq 0 ]
  [ "$output" = "$(printf '%s\n' acp --disable_telemetry)" ]
}

# agy rejects --disable_telemetry outside acp, so every other call must reach it unchanged.
@test "commands other than acp pass their arguments through unchanged" {
  assert_passed_through
  assert_passed_through -p hello
  assert_passed_through help
  assert_passed_through models
  assert_passed_through --version
  assert_passed_through --help
  assert_passed_through mcp list
  assert_passed_through -p acp
}

@test "wrapper refuses to run without the real agy path" {
  run --separate-stderr env -u AGY_BIN /bin/bash "$SCRIPT" acp

  [ "$status" -ne 0 ]
  [[ "$stderr" == *"AGY_BIN is required"* ]]
}
