#!/usr/bin/env bats
# Executable specifications for Moshi host readiness checks.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  MOSHI_HOOK_STUB="$BATS_TEST_TMPDIR/moshi-hook"
  MOSHI_ARGS_FILE="$BATS_TEST_TMPDIR/moshi-hook-args"
}

evaluate_moshi_pairing_check() {
  nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#darwinConfigurations.mbp.config.home-manager.users.kaito.home.activation.moshiPairingCheck.data"
}

create_moshi_hook_stub() {
  /bin/cat >|"$MOSHI_HOOK_STUB" <<'EOF'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
printf '%s\n' "$*" >>"${MOSHI_ARGS_FILE:?}"
case "${1:-}" in
  probe)
    printf '%s\n' "${MOSHI_PROBE_JSON:?}"
    ;;
  status)
    printf '%s\n' "${MOSHI_STATUS_JSON:?}"
    ;;
  *)
    exit 2
    ;;
esac
EOF
  chmod 0700 "$MOSHI_HOOK_STUB"
}

create_probe_json() {
  local _is_running="${1:-true}"
  local _has_gateway="${2:-true}"
  local _host_id="${3-host_test}"

  jq -cn \
    --argjson is_running "$_is_running" \
    --argjson has_gateway "$_has_gateway" \
    --arg host_id "$_host_id" \
    '{
      installed: true,
      running: $is_running,
      gateway: $has_gateway,
      hostId: $host_id
    }'
}

create_status_json() {
  local _is_paired="$1"
  local _codex_status="$2"
  local _secret_store="${3:-keychain}"

  jq -cn \
    --argjson is_paired "$_is_paired" \
    --arg codex_status "$_codex_status" \
    --arg secret_store "$_secret_store" \
    '{
      paired: $is_paired,
      secretStore: $secret_store,
      hooks: [
        {target: "claude", status: "current"},
        {target: "codex", status: $codex_status}
      ]
    }'
}

run_moshi_pairing_check() {
  local _status_json="$1"
  local _probe_json="${2:-$(create_probe_json)}"

  run --separate-stderr evaluate_moshi_pairing_check
  [ "$status" -eq 0 ]
  local _activation_script="$output"
  create_moshi_hook_stub

  run --separate-stderr env \
    MOSHI_ARGS_FILE="$MOSHI_ARGS_FILE" \
    MOSHI_HOOK_BIN="$MOSHI_HOOK_STUB" \
    MOSHI_PROBE_JSON="$_probe_json" \
    MOSHI_STATUS_JSON="$_status_json" \
    /bin/bash -c "$_activation_script"
}

@test "MacBook Pro accepts a paired Keychain-backed Moshi integration" {
  run_moshi_pairing_check "$(create_status_json true current)"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "MacBook Pro accepts a healthy daemon when activation cannot read pairing" {
  run_moshi_pairing_check "$(create_status_json false current)"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "MacBook Pro warns without blocking when the Moshi daemon is not running" {
  run_moshi_pairing_check \
    "$(create_status_json true current)" \
    "$(create_probe_json false)"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi pairing or managed hooks could not be confirmed."* ]]
}

@test "MacBook Pro warns without blocking when the Moshi gateway is unavailable" {
  run_moshi_pairing_check \
    "$(create_status_json true current)" \
    "$(create_probe_json true false)"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi pairing or managed hooks could not be confirmed."* ]]
}

@test "MacBook Pro warns without blocking when Moshi has no host identity" {
  run_moshi_pairing_check \
    "$(create_status_json true current)" \
    "$(create_probe_json true true '')"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi pairing or managed hooks could not be confirmed."* ]]
}

@test "MacBook Pro warns when Moshi credentials are not Keychain-backed" {
  run_moshi_pairing_check "$(create_status_json true current file)"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi pairing or managed hooks could not be confirmed."* ]]
}

@test "MacBook Pro warns when a managed Moshi hook is stale" {
  run_moshi_pairing_check "$(create_status_json true stale)"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi pairing or managed hooks could not be confirmed."* ]]
}

@test "MacBook Pro warns without blocking when moshi-hook is unavailable" {
  run --separate-stderr evaluate_moshi_pairing_check

  [ "$status" -eq 0 ]
  activation_script="$output"

  run --separate-stderr env \
    MOSHI_HOOK_BIN="$BATS_TEST_TMPDIR/missing-moshi-hook" \
    /bin/bash -c "$activation_script"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi pairing or managed hooks could not be confirmed."* ]]
}

@test "Moshi readiness checks use only health subcommands" {
  run_moshi_pairing_check "$(create_status_json true current)"

  [ "$status" -eq 0 ]

  run /bin/cat "$MOSHI_ARGS_FILE"

  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "probe --json" ]
  [ "${lines[1]}" = "status --json" ]
  [ "${#lines[@]}" -eq 2 ]
}

@test "MacBook Air does not inspect Moshi pairing" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#darwinConfigurations.mba.config.home-manager.users.kaito.home.activation" \
    --apply 'activation: builtins.hasAttr "moshiPairingCheck" activation'

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
}
