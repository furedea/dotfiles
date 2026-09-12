#!/usr/bin/env bats
# Executable specifications for the Moshi host lifecycle.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/scripts/moshi/manage_moshi_hook.sh"
  MOSHI_HOOK_STUB="$BATS_TEST_TMPDIR/moshi-hook"
  MOSHI_ARGS_FILE="$BATS_TEST_TMPDIR/moshi-args"
  MOSHI_ATTEMPT_FILE="$BATS_TEST_TMPDIR/moshi-attempts"
  MOSHI_EVENTS_FILE="$BATS_TEST_TMPDIR/moshi-events"
  create_moshi_hook_stub
}

@test "host service waits for Keychain pairing before serving" {
  run env \
    MOSHI_ARGS_FILE="$MOSHI_ARGS_FILE" \
    MOSHI_ATTEMPT_FILE="$MOSHI_ATTEMPT_FILE" \
    MOSHI_EVENTS_FILE="$MOSHI_EVENTS_FILE" \
    MOSHI_HOOK_BIN="$MOSHI_HOOK_STUB" \
    MOSHI_STATUS_FAILURES=1 \
    JQ_BIN="$(command -v jq)" \
    SLEEP_BIN=/usr/bin/true \
    /bin/bash "$SCRIPT" serve

  [ "$status" -eq 0 ]

  run /bin/cat "$MOSHI_ARGS_FILE"

  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "status --json" ]
  [ "${lines[1]}" = "status --json" ]
  [ "${lines[2]}" = "serve" ]
  [ "${#lines[@]}" -eq 3 ]
}
