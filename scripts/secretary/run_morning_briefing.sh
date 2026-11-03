#!/usr/bin/env bash
set -euCo pipefail

function usage() {
  cat <<EOF
Description:
    Run the morning briefing once per day with "claude -p", save the report, and mail it from
    Apple Mail to the address in briefing_address (same account sends to itself).

Usage:
    $0 [--force]

Options:
    --force: run even when a briefing already started today
    --help, -h: print this
EOF
}

readonly CLAUDE_BIN="${CLAUDE_BIN:-claude}"
readonly OSASCRIPT_BIN="${OSASCRIPT_BIN:-/usr/bin/osascript}"
readonly SECRETARY_DIR="${SECRETARY_DIR:?SECRETARY_DIR is required}"
readonly STATE_DIR="${SECRETARY_STATE_DIR:-$HOME/.local/state/secretary}"
readonly TODAY="${SECRETARY_TODAY:-$(date +%Y-%m-%d)}"
readonly LAST_RUN_FILE="$STATE_DIR/last_run_date"
readonly ADDRESS_FILE="$STATE_DIR/briefing_address"
readonly REPORT_FILE="$STATE_DIR/briefings/$TODAY.md"
readonly SUBJECT="[briefing] $TODAY"
readonly FAILURE_SUBJECT="[briefing] $TODAY 失敗"
readonly LOG_HINT="$HOME/Library/Logs/morning-briefing.log"
readonly BRIEFING_PROMPT="Run the morning-briefing skill now. Answer with the Japanese report only."

function log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*"
}

function already_started_today() {
  [ -f "$LAST_RUN_FILE" ] && [ "$(<"$LAST_RUN_FILE")" = "$TODAY" ]
}

function run_briefing() {
  (
    cd "$SECRETARY_DIR"
    "$CLAUDE_BIN" -p "$BRIEFING_PROMPT" \
      --settings "$SECRETARY_DIR/.claude/settings.json" \
      --setting-sources project \
      --permission-mode dontAsk \
      --output-format text
  )
}

function briefing_address() {
  local _address=""
  [ -f "$ADDRESS_FILE" ] && _address="$(head -n 1 "$ADDRESS_FILE")"
  [ -n "$_address" ] || return 1
  printf '%s\n' "$_address"
}

# The message is sent from the Apple Mail account that owns the address, so the provider signs it.
function send_mail() {
  local _subject="$1"
  local _body="$2"
  local _address
  _address="$(briefing_address)" || {
    log "mail not sent: $ADDRESS_FILE is missing or empty"
    return 1
  }
  "$OSASCRIPT_BIN" - "$_address" "$_subject" "$_body" <<'APPLESCRIPT'
on run argv
  set addr to item 1 of argv
  tell application "Mail"
    set hasAccount to false
    repeat with acct in accounts
      if (email addresses of acct) contains addr then set hasAccount to true
    end repeat
    if not hasAccount then error "No Apple Mail account has the address " & addr
    set msg to make new outgoing message with properties {subject:item 2 of argv, content:item 3 of argv, visible:false}
    tell msg
      set sender to addr
      make new to recipient at end of to recipients with properties {address:addr}
      send
    end tell
  end tell
end run
APPLESCRIPT
}

function fail() {
  log "$1"
  send_mail "$FAILURE_SUBJECT" "$1" || true
  exit 1
}

function main() {
  local _force=false
  case "${1:-}" in
    --help | -h)
      usage
      exit 0
      ;;
    --force) _force=true ;;
    "") ;;
    *)
      usage >&2
      exit 1
      ;;
  esac

  mkdir -p "$STATE_DIR/briefings"
  if [ "$_force" = false ] && already_started_today; then
    log "skip: a briefing already started on $TODAY"
    exit 0
  fi
  printf '%s\n' "$TODAY" >|"$LAST_RUN_FILE"

  local _report=""
  if ! _report="$(run_briefing)"; then
    [ -z "$_report" ] || printf '%s\n' "$_report" >|"$REPORT_FILE"
    fail "ブリーフィングの生成に失敗しました．ログ：$LOG_HINT"
  fi
  [ -n "$_report" ] || fail "ブリーフィングが空でした．ログ：$LOG_HINT"
  printf '%s\n' "$_report" >|"$REPORT_FILE"
  log "saved $REPORT_FILE"

  send_mail "$SUBJECT" "$_report" || {
    log "delivery failed; the report stays at $REPORT_FILE"
    exit 1
  }
  log "mailed $SUBJECT"
}

main "$@"
