#!/usr/bin/env bats
# Executable specifications for Moshi host readiness checks.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  MOSHI_HOOK_STUB="$BATS_TEST_TMPDIR/moshi-hook"
  MOSHI_ARGS_FILE="$BATS_TEST_TMPDIR/moshi-hook-args"
  MOSHI_PROBE_ATTEMPT_FILE="$BATS_TEST_TMPDIR/moshi-probe-attempts"
}

evaluate_moshi_check() {
  local _check_name="$1"

  nix eval --no-write-lock-file \
    --extra-experimental-features dynamic-derivations --raw \
    "$REPO_ROOT#darwinConfigurations.mbp.config.home-manager.users.kaito.home.activation.$_check_name.data"
}

create_moshi_hook_stub() {
  /bin/cat >|"$MOSHI_HOOK_STUB" <<'EOF'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
printf '%s\n' "$*" >>"${MOSHI_ARGS_FILE:?}"
case "${1:-}" in
  probe)
    probe_attempt=0
    if [ -f "${MOSHI_PROBE_ATTEMPT_FILE:?}" ]; then
      read -r probe_attempt <"${MOSHI_PROBE_ATTEMPT_FILE:?}"
    fi
    probe_attempt=$((probe_attempt + 1))
    printf '%s\n' "$probe_attempt" >|"${MOSHI_PROBE_ATTEMPT_FILE:?}"
    if ((probe_attempt <= ${MOSHI_PROBE_FAILURES:-0})); then
      printf '%s\n' '{"running":false,"gateway":false,"hostId":""}'
    else
      printf '%s\n' "${MOSHI_PROBE_JSON:?}"
    fi
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

run_moshi_configuration_check() {
  local _status_json="$1"

  run --separate-stderr evaluate_moshi_check moshiConfigurationCheck
  [ "$status" -eq 0 ]
  local _activation_script="$output"
  create_moshi_hook_stub

  run --separate-stderr env \
    MOSHI_ARGS_FILE="$MOSHI_ARGS_FILE" \
    MOSHI_HOOK_BIN="$MOSHI_HOOK_STUB" \
    MOSHI_STATUS_JSON="$_status_json" \
    /bin/bash -c "$_activation_script"
}

run_moshi_runtime_check() {
  local _probe_json="$1"
  local _probe_failures="${2:-0}"

  run --separate-stderr evaluate_moshi_check moshiRuntimeCheck
  [ "$status" -eq 0 ]
  local _activation_script="$output"
  create_moshi_hook_stub

  run --separate-stderr env \
    MOSHI_ARGS_FILE="$MOSHI_ARGS_FILE" \
    MOSHI_HOOK_BIN="$MOSHI_HOOK_STUB" \
    MOSHI_PROBE_ATTEMPT_FILE="$MOSHI_PROBE_ATTEMPT_FILE" \
    MOSHI_PROBE_FAILURES="$_probe_failures" \
    MOSHI_PROBE_JSON="$_probe_json" \
    MOSHI_SLEEP_BIN=/usr/bin/true \
    /bin/bash -c "$_activation_script"
}

@test "MacBook Pro accepts Keychain-backed current Moshi hooks" {
  run_moshi_configuration_check "$(create_status_json true current)"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "Moshi configuration check does not depend on pairing visibility" {
  run_moshi_configuration_check "$(create_status_json false current)"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "MacBook Pro reports the configuration warning for non-Keychain credentials" {
  run_moshi_configuration_check "$(create_status_json true current file)"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi Keychain storage or managed hooks could not be confirmed."* ]]
  [[ "$stderr" != *"Moshi daemon readiness could not be confirmed."* ]]
}

@test "MacBook Pro reports the configuration warning for a stale managed hook" {
  run_moshi_configuration_check "$(create_status_json true stale)"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi Keychain storage or managed hooks could not be confirmed."* ]]
  [[ "$stderr" != *"Moshi daemon readiness could not be confirmed."* ]]
}

@test "MacBook Pro accepts a ready Moshi daemon" {
  run_moshi_runtime_check "$(create_probe_json)"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "MacBook Pro reports the runtime warning when the Moshi daemon is not running" {
  run_moshi_runtime_check "$(create_probe_json false)"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi daemon readiness could not be confirmed."* ]]
  [[ "$stderr" != *"Moshi Keychain storage or managed hooks could not be confirmed."* ]]
}

@test "MacBook Pro reports the runtime warning when the Moshi gateway is unavailable" {
  run_moshi_runtime_check "$(create_probe_json true false)"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi daemon readiness could not be confirmed."* ]]
}

@test "MacBook Pro reports the runtime warning when Moshi has no host identity" {
  run_moshi_runtime_check "$(create_probe_json true true '')"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"Moshi daemon readiness could not be confirmed."* ]]
}

@test "Moshi runtime check retries while launchd starts the daemon" {
  run_moshi_runtime_check "$(create_probe_json)" 2

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]

  run /bin/cat "$MOSHI_PROBE_ATTEMPT_FILE"
  [ "$status" -eq 0 ]
  [ "$output" = "3" ]
}

@test "Moshi checks use their corresponding read-only health subcommands" {
  run_moshi_configuration_check "$(create_status_json true current)"

  [ "$status" -eq 0 ]

  run_moshi_runtime_check "$(create_probe_json)"

  [ "$status" -eq 0 ]

  run /bin/cat "$MOSHI_ARGS_FILE"

  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "status --json" ]
  [ "${lines[1]}" = "probe --json" ]
  [ "${#lines[@]}" -eq 2 ]
}

@test "MacBook Air does not inspect Moshi configuration or runtime" {
  run --separate-stderr nix eval --no-write-lock-file \
    --extra-experimental-features dynamic-derivations --json \
    "$REPO_ROOT#darwinConfigurations.mba.config.home-manager.users.kaito.home.activation" \
    --apply 'activation: builtins.filter (name: builtins.match "moshi.*Check" name != null) (builtins.attrNames activation)'

  [ "$status" -eq 0 ]
  [ "$output" = "[]" ]
}

@test "Moshi runtime check runs after LaunchAgents are configured" {
  run --separate-stderr nix eval --no-write-lock-file \
    --extra-experimental-features dynamic-derivations --json \
    "$REPO_ROOT#darwinConfigurations.mbp.config.home-manager.users.kaito.home.activation.moshiRuntimeCheck.after"

  [ "$status" -eq 0 ]
  [ "$output" = '["setupLaunchAgents"]' ]
}

@test "Moshi configuration check runs after managed hooks are linked" {
  run --separate-stderr nix eval --no-write-lock-file \
    --extra-experimental-features dynamic-derivations --json \
    "$REPO_ROOT#darwinConfigurations.mbp.config.home-manager.users.kaito.home.activation.moshiConfigurationCheck.after"

  [ "$status" -eq 0 ]
  [ "$output" = '["linkGeneration"]' ]
}
