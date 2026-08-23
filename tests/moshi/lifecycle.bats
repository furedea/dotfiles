#!/usr/bin/env bats
# Executable specifications for the Moshi host lifecycle.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/scripts/moshi/manage_moshi_hook.sh"
  MOSHI_HOOK_STUB="$BATS_TEST_TMPDIR/moshi-hook"
  MOSHI_ARGS_FILE="$BATS_TEST_TMPDIR/moshi-args"
  MOSHI_ATTEMPT_FILE="$BATS_TEST_TMPDIR/moshi-attempts"
  MOSHI_PROBE_ATTEMPT_FILE="$BATS_TEST_TMPDIR/moshi-probe-attempts"
  MOSHI_EVENTS_FILE="$BATS_TEST_TMPDIR/moshi-events"
  LAUNCHCTL_STUB="$BATS_TEST_TMPDIR/launchctl"
  BREW_STUB="$BATS_TEST_TMPDIR/brew"
  LEGACY_SERVICE_FILE="$BATS_TEST_TMPDIR/homebrew.mxcl.moshi-hook.plist"
  RUNTIME_STATE_FILE="$BATS_TEST_TMPDIR/runtime-path"
  create_moshi_hook_stub
  create_launchctl_stub
  create_brew_stub
}

@test "host service waits for Keychain pairing before serving" {
  run env \
    MOSHI_ARGS_FILE="$MOSHI_ARGS_FILE" \
    MOSHI_ATTEMPT_FILE="$MOSHI_ATTEMPT_FILE" \
    MOSHI_EVENTS_FILE="$MOSHI_EVENTS_FILE" \
    MOSHI_HOOK_BIN="$MOSHI_HOOK_STUB" \
    MOSHI_RUNTIME_STATE_FILE="$RUNTIME_STATE_FILE" \
    MOSHI_STATUS_FAILURES=1 \
    JQ_BIN="$(command -v jq)" \
    REALPATH_BIN="$(command -v realpath)" \
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

@test "formula update keeps the old service until Keychain pairing is readable" {
  run env \
    MOSHI_ARGS_FILE="$MOSHI_ARGS_FILE" \
    MOSHI_ATTEMPT_FILE="$MOSHI_ATTEMPT_FILE" \
    MOSHI_EVENTS_FILE="$MOSHI_EVENTS_FILE" \
    MOSHI_HOOK_BIN="$MOSHI_HOOK_STUB" \
    MOSHI_PROBE_ATTEMPT_FILE="$MOSHI_PROBE_ATTEMPT_FILE" \
    MOSHI_RUNTIME_STATE_FILE="$RUNTIME_STATE_FILE" \
    MOSHI_STATUS_FAILURES=1 \
    JQ_BIN="$(command -v jq)" \
    LAUNCHCTL_BIN="$LAUNCHCTL_STUB" \
    MOSHI_SERVICE_LABEL=org.nix-community.home.moshi-hook \
    REALPATH_BIN="$(command -v realpath)" \
    SLEEP_BIN=/usr/bin/true \
    USER_ID=501 \
    /bin/bash "$SCRIPT" restart-after-update

  [ "$status" -eq 0 ]

  run /bin/cat "$MOSHI_EVENTS_FILE"

  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "moshi:status --json" ]
  [ "${lines[1]}" = "moshi:status --json" ]
  [ "${lines[2]}" = "launchctl:kickstart -k gui/501/org.nix-community.home.moshi-hook" ]
  [ "${lines[3]}" = "moshi:probe --json" ]
  [ "${#lines[@]}" -eq 4 ]
}

@test "migration stops the legacy Homebrew service without changing pairing" {
  touch "$LEGACY_SERVICE_FILE"

  run env \
    BREW_BIN="$BREW_STUB" \
    MOSHI_EVENTS_FILE="$MOSHI_EVENTS_FILE" \
    MOSHI_LEGACY_SERVICE_FILE="$LEGACY_SERVICE_FILE" \
    /bin/bash "$SCRIPT" migrate-homebrew-service

  [ "$status" -eq 0 ]

  run /bin/cat "$MOSHI_EVENTS_FILE"

  [ "$status" -eq 0 ]
  [ "$output" = "brew:services stop rjyo/moshi/moshi-hook" ]
}

@test "migration leaves Homebrew alone after the legacy service is gone" {
  run env \
    BREW_BIN="$BREW_STUB" \
    MOSHI_EVENTS_FILE="$MOSHI_EVENTS_FILE" \
    MOSHI_LEGACY_SERVICE_FILE="$LEGACY_SERVICE_FILE" \
    /bin/bash "$SCRIPT" migrate-homebrew-service

  [ "$status" -eq 0 ]
  [ ! -e "$MOSHI_EVENTS_FILE" ]
}

@test "formula path events do not restart an unchanged runtime" {
  "$(command -v realpath)" "$MOSHI_HOOK_STUB" >|"$RUNTIME_STATE_FILE"

  run env \
    MOSHI_ARGS_FILE="$MOSHI_ARGS_FILE" \
    MOSHI_ATTEMPT_FILE="$MOSHI_ATTEMPT_FILE" \
    MOSHI_EVENTS_FILE="$MOSHI_EVENTS_FILE" \
    MOSHI_HOOK_BIN="$MOSHI_HOOK_STUB" \
    MOSHI_RUNTIME_STATE_FILE="$RUNTIME_STATE_FILE" \
    JQ_BIN="$(command -v jq)" \
    LAUNCHCTL_BIN="$LAUNCHCTL_STUB" \
    REALPATH_BIN="$(command -v realpath)" \
    SLEEP_BIN=/usr/bin/true \
    USER_ID=501 \
    /bin/bash "$SCRIPT" restart-after-update

  [ "$status" -eq 0 ]
  [ ! -e "$MOSHI_EVENTS_FILE" ]
}

@test "formula update records the runtime only after its gateway is ready" {
  run env \
    MOSHI_ARGS_FILE="$MOSHI_ARGS_FILE" \
    MOSHI_ATTEMPT_FILE="$MOSHI_ATTEMPT_FILE" \
    MOSHI_EVENTS_FILE="$MOSHI_EVENTS_FILE" \
    MOSHI_HOOK_BIN="$MOSHI_HOOK_STUB" \
    MOSHI_PROBE_ATTEMPT_FILE="$MOSHI_PROBE_ATTEMPT_FILE" \
    MOSHI_PROBE_FAILURES=1 \
    MOSHI_RUNTIME_STATE_FILE="$RUNTIME_STATE_FILE" \
    JQ_BIN="$(command -v jq)" \
    LAUNCHCTL_BIN="$LAUNCHCTL_STUB" \
    REALPATH_BIN="$(command -v realpath)" \
    SLEEP_BIN=/usr/bin/true \
    USER_ID=501 \
    /bin/bash "$SCRIPT" restart-after-update

  [ "$status" -eq 0 ]

  run /bin/cat "$MOSHI_EVENTS_FILE"

  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "moshi:status --json" ]
  [ "${lines[1]}" = "launchctl:kickstart -k gui/501/org.nix-community.home.moshi-hook" ]
  [ "${lines[2]}" = "moshi:probe --json" ]
  [ "${lines[3]}" = "moshi:probe --json" ]
  [ "${#lines[@]}" -eq 4 ]
}
