#!/usr/bin/env bats
# Executable specifications for the authenticated Hister server launcher.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/scripts/hister/run_hister_server.sh"
  SECURITY_STUB="$BATS_TEST_TMPDIR/security"
  HISTER_STUB="$BATS_TEST_TMPDIR/hister"
  SECURITY_ARGS_FILE="$BATS_TEST_TMPDIR/security-args"
  HISTER_EVENTS_FILE="$BATS_TEST_TMPDIR/hister-events"
  create_security_stub
  create_hister_stub
}

@test "server refuses to start when the Keychain token is unavailable" {
  run env \
    HISTER_EVENTS_FILE="$HISTER_EVENTS_FILE" \
    HISTER_SECURITY_ARGS_FILE="$SECURITY_ARGS_FILE" \
    HISTER_SECURITY_BIN="$SECURITY_STUB" \
    HISTER_SECURITY_UNAVAILABLE=true \
    /bin/bash "$SCRIPT" "$HISTER_STUB" kaito

  [ "$status" -ne 0 ]
  [[ "$output" == *"Hister access token is unavailable"* ]]
  [ ! -e "$HISTER_EVENTS_FILE" ]
}

@test "server refuses to start when the Keychain token is empty" {
  run env \
    HISTER_EVENTS_FILE="$HISTER_EVENTS_FILE" \
    HISTER_SECURITY_ARGS_FILE="$SECURITY_ARGS_FILE" \
    HISTER_SECURITY_BIN="$SECURITY_STUB" \
    HISTER_SECURITY_EMPTY=true \
    /bin/bash "$SCRIPT" "$HISTER_STUB" kaito

  [ "$status" -ne 0 ]
  [[ "$output" == *"Hister access token is unavailable"* ]]
  [ ! -e "$HISTER_EVENTS_FILE" ]
}

@test "server receives the Keychain token without logging it" {
  run env \
    HISTER_EVENTS_FILE="$HISTER_EVENTS_FILE" \
    HISTER_SECURITY_ARGS_FILE="$SECURITY_ARGS_FILE" \
    HISTER_SECURITY_BIN="$SECURITY_STUB" \
    /bin/bash "$SCRIPT" "$HISTER_STUB" kaito

  [ "$status" -eq 0 ]
  [[ "$output" != *"test-hister-credential"* ]]

  run /bin/cat "$SECURITY_ARGS_FILE"
  [ "$status" -eq 0 ]
  [ "$output" = \
    "find-generic-password -a kaito -s org.furedea.hister.access-token -w" ]

  run /bin/cat "$HISTER_EVENTS_FILE"
  [ "$status" -eq 0 ]
  [ "$output" = "listen" ]
}
