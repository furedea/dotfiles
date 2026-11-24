#!/usr/bin/env bats
# Executable specifications for the check that T3 Code is kept from sending telemetry.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/scripts/t3/check_telemetry.sh"
  JQ_BIN="$(command -v jq)"
  export JQ_BIN
  export STATE_DIR="$BATS_TEST_TMPDIR/state"
  export POLICY_FILE="$BATS_TEST_TMPDIR/policy.json"
  export HOSTS_FILE="$BATS_TEST_TMPDIR/hosts"
  export BLOCKED_HOSTS="ingest.t3.codes api.axiom.co"
  export LAUNCHCTL_BIN="$BATS_TEST_TMPDIR/launchctl"
  export SERVICE_LABEL=""
  PACKAGE="$BATS_TEST_TMPDIR/t3code-1"
  write_good_state
  write_package "$PACKAGE" 'fetch("https://app.t3.codes"); process.env.T3CODE_HOME'
}

write_good_state() {
  printf '%s' '{"schemaVersion":1,"organization":"me","limits":{"telemetry":false}}' >"$POLICY_FILE"
  printf '%s\n' '127.0.0.1 localhost' \
    '0.0.0.0 ingest.t3.codes' ':: ingest.t3.codes' \
    '0.0.0.0 api.axiom.co' ':: api.axiom.co' >"$HOSTS_FILE"
  cat >"$LAUNCHCTL_BIN" <<'EOS'
#!/usr/bin/env bash
case "$1" in
  getenv) echo "${FAKE_GETENV-false}" ;;
  print) printf '\tenvironment = {\n\t\tT3CODE_TELEMETRY_ENABLED => %s\n\t}\n' "${FAKE_SERVICE_VALUE-false}" ;;
esac
EOS
  chmod +x "$LAUNCHCTL_BIN"
}

write_package() {
  local _dist="$1/libexec/t3code/apps/server/dist"
  mkdir -p "$_dist"
  printf '%s\n' "$2" >"$_dist/main.mjs"
}

@test "a correct setup produces no warning and exits 0" {
  run --separate-stderr "$SCRIPT" "$PACKAGE"

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
}

@test "the result and package are recorded under the state directory" {
  run "$SCRIPT" "$PACKAGE"

  grep -qxF "package=$PACKAGE" "$STATE_DIR/last_check.txt"
  grep -qxF "warnings=0" "$STATE_DIR/last_check.txt"
  [ "$(cat "$STATE_DIR/checked_package")" = "$PACKAGE" ]
}

@test "a package is not recorded as checked while a warning remains" {
  rm "$POLICY_FILE"

  run "$SCRIPT" "$PACKAGE"

  [ ! -e "$STATE_DIR/checked_package" ]
}

@test "a warning removes the record of an earlier clean check of the same package" {
  "$SCRIPT" "$PACKAGE"
  [ -e "$STATE_DIR/checked_package" ]
  rm "$POLICY_FILE"

  run "$SCRIPT" "$PACKAGE"

  [ ! -e "$STATE_DIR/checked_package" ]
}

@test "the package is recorded once the warnings are gone" {
  rm "$POLICY_FILE"
  "$SCRIPT" "$PACKAGE" 2>/dev/null
  write_good_state

  run "$SCRIPT" "$PACKAGE"

  [ "$(cat "$STATE_DIR/checked_package")" = "$PACKAGE" ]
}

@test "a missing policy warns and still exits 0" {
  rm "$POLICY_FILE"

  run --separate-stderr "$SCRIPT" "$PACKAGE"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"policy"*"missing"* ]]
  grep -q '^warning=.*missing' "$STATE_DIR/last_check.txt"
}

@test "a policy that leaves telemetry on warns" {
  printf '%s' '{"schemaVersion":1,"organization":"me","limits":{"telemetry":true}}' >"$POLICY_FILE"

  run --separate-stderr "$SCRIPT" "$PACKAGE"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"limits.telemetry false"* ]]
}

@test "a policy without an organization warns" {
  printf '%s' '{"schemaVersion":1,"limits":{"telemetry":false}}' >"$POLICY_FILE"

  run --separate-stderr "$SCRIPT" "$PACKAGE"

  [[ "$stderr" == *"organization"* ]]
}

@test "an invalid policy file warns instead of failing" {
  printf '%s' 'not json' >"$POLICY_FILE"

  run --separate-stderr "$SCRIPT" "$PACKAGE"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"limits.telemetry false"* ]]
}

@test "a host missing its IPv6 line warns for that host and address" {
  printf '%s\n' '0.0.0.0 ingest.t3.codes' '0.0.0.0 api.axiom.co' ':: api.axiom.co' >"$HOSTS_FILE"

  run --separate-stderr "$SCRIPT" "$PACKAGE"

  [[ "$stderr" == *"ingest.t3.codes to ::"* ]]
  [[ "$stderr" != *"api.axiom.co"* ]]
}

@test "a commented-out hosts line does not count as a block" {
  printf '%s\n' '# 0.0.0.0 ingest.t3.codes' ':: ingest.t3.codes' \
    '0.0.0.0 api.axiom.co' ':: api.axiom.co' >"$HOSTS_FILE"

  run --separate-stderr "$SCRIPT" "$PACKAGE"

  [[ "$stderr" == *"ingest.t3.codes to 0.0.0.0"* ]]
}

@test "an unset launchctl variable warns" {
  FAKE_GETENV="" run --separate-stderr "$SCRIPT" "$PACKAGE"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"launchctl getenv T3CODE_TELEMETRY_ENABLED"* ]]
}

@test "the server agent is checked only when its label is given" {
  FAKE_SERVICE_VALUE=true run --separate-stderr "$SCRIPT" "$PACKAGE"
  [ -z "$stderr" ]

  SERVICE_LABEL=org.example.t3 FAKE_SERVICE_VALUE=true run --separate-stderr "$SCRIPT" "$PACKAGE"
  [[ "$stderr" == *"org.example.t3 does not run with T3CODE_TELEMETRY_ENABLED => false"* ]]
}

@test "a server agent running with the variable false does not warn" {
  SERVICE_LABEL=org.example.t3 run --separate-stderr "$SCRIPT" "$PACKAGE"

  [ -z "$stderr" ]
}

@test "the first scan records a baseline without a diff warning" {
  run "$SCRIPT" "$PACKAGE"

  grep -qxF "host app.t3.codes" "$STATE_DIR/bundled_names.txt"
  grep -qxF "variable T3CODE_HOME" "$STATE_DIR/bundled_names.txt"
}

@test "a new host and a new variable in the next version are warned about" {
  "$SCRIPT" "$PACKAGE"
  local _next="$BATS_TEST_TMPDIR/t3code-2"
  write_package "$_next" 'fetch("https://app.t3.codes"); fetch("https://track.example.com/x"); process.env.T3CODE_HOME; process.env.OTEL_EXPORTER_OTLP_ENDPOINT'

  run --separate-stderr "$SCRIPT" "$_next"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"host track.example.com"* ]]
  [[ "$stderr" == *"variable OTEL_EXPORTER_OTLP_ENDPOINT"* ]]
  [[ "$stderr" != *"app.t3.codes"* ]]
}

@test "an unchanged bundle in a new store path does not warn" {
  "$SCRIPT" "$PACKAGE"
  local _next="$BATS_TEST_TMPDIR/t3code-2"
  write_package "$_next" 'fetch("https://app.t3.codes"); process.env.T3CODE_HOME'

  run --separate-stderr "$SCRIPT" "$_next"

  [ -z "$stderr" ]
}

@test "a package without a server bundle warns and keeps the previous baseline" {
  "$SCRIPT" "$PACKAGE"

  run --separate-stderr "$SCRIPT" "$BATS_TEST_TMPDIR/empty"

  [ "$status" -eq 0 ]
  [[ "$stderr" == *"no server bundle"* ]]
  grep -qxF "host app.t3.codes" "$STATE_DIR/bundled_names.txt"
}

@test "missing arguments print usage and fail" {
  run --separate-stderr "$SCRIPT"

  [ "$status" -eq 1 ]
  [[ "$stderr" == *Usage:* ]]
}
