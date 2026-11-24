#!/usr/bin/env bash
set -euo pipefail

function usage() {
  cat <<EOF2
Description:
    Check that T3 Code is kept from sending telemetry, and record the result. Every problem
    is a warning on stderr; the exit status is 0 so that a switch never fails on it.
    The bundled JS of the T3 package is scanned for https:// hosts and T3CODE_* / OTEL*
    variable names; names not seen in the last scan are warned about as new.

Usage:
    $0 <T3_PACKAGE>

Environment:
    JQ_BIN: jq executable (required)
    STATE_DIR: where results are recorded (default: ~/.local/state/t3-telemetry)
    POLICY_FILE: managed policy (default: /Library/Application Support/T3Code/policy.json)
    HOSTS_FILE: hosts file (default: /etc/hosts)
    BLOCKED_HOSTS: space-separated hosts that must resolve to 0.0.0.0 and :: (required)
    LAUNCHCTL_BIN: launchctl executable (default: /bin/launchctl)
    SERVICE_LABEL: launchd label of the T3 server agent to check; unset skips that check

Options:
    --help, -h: print this
EOF2
}

readonly JQ_BIN="${JQ_BIN:?JQ_BIN is required}"
readonly BLOCKED_HOSTS="${BLOCKED_HOSTS:?BLOCKED_HOSTS is required}"
readonly STATE_DIR="${STATE_DIR:-$HOME/.local/state/t3-telemetry}"
readonly POLICY_FILE="${POLICY_FILE:-/Library/Application Support/T3Code/policy.json}"
readonly HOSTS_FILE="${HOSTS_FILE:-/etc/hosts}"
readonly LAUNCHCTL_BIN="${LAUNCHCTL_BIN:-/bin/launchctl}"
readonly SERVICE_LABEL="${SERVICE_LABEL:-}"
readonly ENV_NAME="T3CODE_TELEMETRY_ENABLED"

warnings=()

function main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
  fi
  if [[ "$#" -ne 1 ]]; then
    usage >&2
    exit 1
  fi

  local _package="$1"
  mkdir -p "$STATE_DIR"

  check_policy
  check_hosts
  check_launchctl_environment
  if [[ -n "$SERVICE_LABEL" ]]; then
    check_service_environment
  fi
  check_bundled_names "$_package"
  record_result "$_package"
  return 0
}

function warn() {
  warnings+=("$1")
  echo "t3-telemetry: warning: $1" >&2
}

function check_policy() {
  if [[ ! -f "$POLICY_FILE" ]]; then
    warn "managed policy $POLICY_FILE is missing"
    return 0
  fi
  if ! "$JQ_BIN" -e '
      .schemaVersion == 1
      and ((.organization | type) == "string" and (.organization | length) > 0)
      and .limits.telemetry == false' "$POLICY_FILE" >/dev/null 2>&1; then
    warn "managed policy $POLICY_FILE does not set schemaVersion 1, an organization, and limits.telemetry false"
  fi
}

function check_hosts() {
  local _host
  for _host in $BLOCKED_HOSTS; do
    if ! resolves_to "0.0.0.0" "$_host"; then
      warn "$HOSTS_FILE does not map $_host to 0.0.0.0"
    fi
    if ! resolves_to "::" "$_host"; then
      warn "$HOSTS_FILE does not map $_host to ::"
    fi
  done
}

function resolves_to() {
  [[ -r "$HOSTS_FILE" ]] &&
    awk -v address="$1" -v host="$2" '
      $0 !~ /^[[:space:]]*#/ && $1 == address {
        for (i = 2; i <= NF; i++) {
          if ($i == host) { found = 1 }
          if ($i ~ /^#/) { break }
        }
      }
      END { exit found ? 0 : 1 }' "$HOSTS_FILE"
}

function check_launchctl_environment() {
  local _value
  _value=$("$LAUNCHCTL_BIN" getenv "$ENV_NAME" 2>/dev/null || true)
  if [[ "$_value" != "false" ]]; then
    warn "launchctl getenv $ENV_NAME is '$_value', not 'false' (desktop apps launched from the Dock miss the opt-out)"
  fi
}

function check_service_environment() {
  local _description
  _description=$("$LAUNCHCTL_BIN" print "gui/$(id -u)/$SERVICE_LABEL" 2>/dev/null || true)
  if ! grep -Eq "^[[:space:]]*$ENV_NAME => false$" <<<"$_description"; then
    warn "$SERVICE_LABEL does not run with $ENV_NAME => false (not loaded, or loaded from an old plist)"
  fi
}

# Print the https:// hosts and the T3CODE_* / OTEL* names found in the package's server bundle.
function scan_bundle() {
  local _bundle="$1/libexec/t3code/apps/server/dist"
  if [[ ! -d "$_bundle" ]]; then
    return 1
  fi
  {
    grep -rhoE --include='*.mjs' --include='*.js' --include='*.cjs' 'https://[A-Za-z0-9.-]+' "$_bundle" |
      sed -e 's|^https://|host |' || true
    grep -rhoE --include='*.mjs' --include='*.js' --include='*.cjs' '\b(T3CODE_[A-Z0-9_]+|OTEL[A-Z0-9_]*)\b' "$_bundle" |
      sed -e 's|^|variable |' || true
  } | sort -u
}

function check_bundled_names() {
  local _package="$1"
  local _current="$STATE_DIR/bundled_names.txt"
  local _scan="$STATE_DIR/bundled_names.new"

  if ! scan_bundle "$_package" >"$_scan"; then
    rm -f "$_scan"
    warn "no server bundle under $_package/libexec/t3code/apps/server/dist; endpoints were not scanned"
    return 0
  fi
  if [[ -f "$_current" ]]; then
    local _added
    _added=$(comm -13 "$_current" "$_scan" | tr '\n' ',' | sed -e 's/,$//')
    if [[ -n "$_added" ]]; then
      warn "new hosts or variables in $_package since the last check: $_added"
    fi
  fi
  mv -f "$_scan" "$_current"
}

function record_result() {
  local _package="$1"
  {
    printf 'checked_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'package=%s\n' "$_package"
    printf 'warnings=%s\n' "${#warnings[@]}"
    local _warning
    for _warning in ${warnings[@]+"${warnings[@]}"}; do
      printf 'warning=%s\n' "$_warning"
    done
  } >"$STATE_DIR/last_check.txt"
  printf '%s\n' "$_package" >"$STATE_DIR/checked_package"
}

main "$@"
