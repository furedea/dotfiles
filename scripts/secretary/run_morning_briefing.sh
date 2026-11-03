#!/usr/bin/env bash
set -euCo pipefail

function usage() {
  cat <<EOF
Description:
    Run the morning briefing once per day with "claude -p", save the report, publish it to the
    fixed Artifact, and notify through an Apple Reminder.

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
readonly REMINDER_PREFIX="朝のブリーフィング"
readonly REMINDER_NAME="$REMINDER_PREFIX $TODAY"
readonly LAST_RUN_FILE="$STATE_DIR/last_run_date"
readonly ARTIFACT_URL_FILE="$STATE_DIR/artifact_url"
readonly ARTIFACT_DIR="$STATE_DIR/artifact"
readonly REPORT_FILE="$STATE_DIR/briefings/$TODAY.md"
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
      --permission-mode dontAsk \
      --output-format text
  )
}

function publish_prompt() {
  local _known_url=""
  if [ -f "$ARTIFACT_URL_FILE" ]; then
    _known_url="$(<"$ARTIFACT_URL_FILE")"
  fi
  printf 'Publish the Markdown report at %s as a private Artifact titled "Morning Briefing".\n' "$REPORT_FILE"
  printf 'Render it to a self-contained HTML page at %s/briefing.html first.\n' "$ARTIFACT_DIR"
  if [ -n "$_known_url" ]; then
    printf 'Update the existing Artifact %s in place: read it first, then publish with that url.\n' "$_known_url"
  else
    printf 'Create a new Artifact.\n'
  fi
  printf 'Reply with exactly one line: ARTIFACT_URL=<claude.ai artifact url>\n'
}

# Runs outside SECRETARY_DIR so the read-only briefing settings do not merge with the publish settings.
function publish_artifact() {
  local _output
  mkdir -p "$ARTIFACT_DIR"
  _output="$(
    cd "$ARTIFACT_DIR"
    "$CLAUDE_BIN" -p "$(publish_prompt)" \
      --settings "$SECRETARY_DIR/publish.settings.json" \
      --permission-mode dontAsk \
      --output-format text
  )" || return 1
  printf '%s\n' "$_output" | grep -Eo 'https://claude\.ai/[^[:space:]]+' | tail -n 1
}

function create_reminder() {
  local _title="$1"
  local _note="$2"
  "$OSASCRIPT_BIN" - "$_title" "$_note" <<'APPLESCRIPT'
on run argv
  set dueDate to (current date) + 60
  tell application "Reminders"
    make new reminder with properties {name:item 1 of argv, body:item 2 of argv, remind me date:dueDate}
  end tell
end run
APPLESCRIPT
}

function complete_previous_reminders() {
  "$OSASCRIPT_BIN" - "$REMINDER_PREFIX" <<'APPLESCRIPT'
on run argv
  tell application "Reminders"
    repeat with staleReminder in (every reminder whose completed is false and name starts with (item 1 of argv))
      set completed of staleReminder to true
    end repeat
  end tell
end run
APPLESCRIPT
}

function notify() {
  create_reminder "$REMINDER_NAME" "$1" || log "reminder creation failed"
}

function fail() {
  log "$1"
  notify "$1"
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

  complete_previous_reminders || log "previous reminders were not completed"

  local _report
  _report="$(run_briefing)" || fail "ブリーフィングの生成に失敗しました．ログ: $LOG_HINT"
  [ -n "$_report" ] || fail "ブリーフィングが空でした．ログ: $LOG_HINT"
  printf '%s\n' "$_report" >|"$REPORT_FILE"
  log "saved $REPORT_FILE"

  local _url
  _url="$(publish_artifact)" || _url=""
  [ -n "$_url" ] || fail "Artifact の公開に失敗しました．ローカル保存: $REPORT_FILE"
  printf '%s\n' "$_url" >|"$ARTIFACT_URL_FILE"
  log "published $_url"
  notify "$_url"
}

main "$@"
