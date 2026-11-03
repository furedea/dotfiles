#!/usr/bin/env bash
set -euCo pipefail

function usage() {
  cat <<EOF
Description:
    Export today's Calendar events with EventKit, run the morning briefing once per day with
    "claude -p", save the report, and mail it from
    Apple Mail to the address in briefing_address (same account sends to itself).

Usage:
    $0 [--force | --resend]

Options:
    --force: run even when a briefing already started today
    --resend: mail today's saved report again without generating it
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
readonly CALENDAR_FILE="$STATE_DIR/calendar/$TODAY.json"
readonly SUBJECT="[briefing] $TODAY"
readonly PARTIAL_SUBJECT="[briefing] ${TODAY}（一部取得失敗）"
readonly RETRY_DELAY_SECONDS="${SECRETARY_RETRY_DELAY_SECONDS:-10}"
readonly COVERAGE_COMPLETE="coverage: complete"
readonly FAILURE_SUBJECT="[briefing] $TODAY 失敗"
readonly LOG_HINT="$HOME/Library/Logs/morning-briefing.log"
readonly BRIEFING_PROMPT="Run the morning-briefing skill now. Answer with the Japanese report only."

function log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*"
}

function already_started_today() {
  [ -f "$LAST_RUN_FILE" ] && [ "$(<"$LAST_RUN_FILE")" = "$TODAY" ]
}

# EventKit expands recurring events; AppleScript's Calendar dictionary does not.
# Failures become {"ok":false,"error":...} so the briefing can report a coverage gap.
function export_calendar() {
  local _json=""
  mkdir -p "$(dirname "$CALENDAR_FILE")"
  if _json="$(run_calendar_script)" && [[ "$_json" == '{"ok":true,'* ]]; then
    printf '%s\n' "$_json" >|"$CALENDAR_FILE"
    log "exported calendar to $CALENDAR_FILE"
    return 0
  fi
  local _reason="${_json:-calendar export failed}"
  printf '{"ok":false,"error":%s}\n' "$(json_string "$_reason")" >|"$CALENDAR_FILE"
  log "calendar export failed: $_reason"
}

function json_string() {
  local _text="${1//\\/\\\\}"
  _text="${_text//\"/\\\"}"
  _text="${_text//$'\n'/ }"
  _text="${_text//$'\t'/ }"
  printf '"%s"' "$_text"
}

function run_calendar_script() {
  "$OSASCRIPT_BIN" -l JavaScript - <<'JXA' 2>&1
ObjC.import('EventKit');
ObjC.import('Foundation');

function pad(n) { return (n < 10 ? '0' : '') + n; }

function localIso(date) {
  const offset = -date.getTimezoneOffset();
  const sign = offset < 0 ? '-' : '+';
  const abs = Math.abs(offset);
  return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) +
    'T' + pad(date.getHours()) + ':' + pad(date.getMinutes()) + ':' + pad(date.getSeconds()) +
    sign + pad(Math.floor(abs / 60)) + ':' + pad(abs % 60);
}

function toDate(nsDate) {
  return new Date(nsDate.timeIntervalSince1970 * 1000);
}

function hasAccess(store) {
  const status = $.EKEventStore.authorizationStatusForEntityType($.EKEntityTypeEvent);
  if (status === 3 || status === 2) return true;
  if (status !== 0) return false;
  let granted = false;
  let done = false;
  store.requestFullAccessToEventsWithCompletion(function (ok) { granted = ok; done = true; });
  const deadline = Date.now() + 60000;
  while (!done && Date.now() < deadline) {
    $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(0.2));
  }
  return granted;
}

function readEvents(store, start, end) {
  const predicate = store.predicateForEventsWithStartDateEndDateCalendars(start, end, $());
  const found = store.eventsMatchingPredicate(predicate)
    .sortedArrayUsingSelector('compareStartDateWithEvent:');
  const events = [];
  for (let i = 0; i < found.count; i++) {
    const event = found.objectAtIndex(i);
    const location = event.location;
    events.push({
      calendar: ObjC.unwrap(event.calendar.title),
      title: ObjC.unwrap(event.title),
      start: localIso(toDate(event.startDate)),
      end: localIso(toDate(event.endDate)),
      allDay: event.allDay,
      location: location.isNil() ? '' : ObjC.unwrap(location),
    });
  }
  return events;
}

function run() {
  try {
    const store = $.EKEventStore.alloc.init;
    if (!hasAccess(store)) {
      return JSON.stringify({ ok: false, error: 'Calendar access is not granted' });
    }
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const end = new Date(start.getTime());
    end.setDate(end.getDate() + 1);
    const nsStart = $.NSDate.dateWithTimeIntervalSince1970(start.getTime() / 1000);
    const nsEnd = $.NSDate.dateWithTimeIntervalSince1970(end.getTime() / 1000);
    return JSON.stringify({ ok: true, events: readEvents(store, nsStart, nsEnd) });
  } catch (e) {
    return JSON.stringify({ ok: false, error: String(e) });
  }
}
JXA
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
  send_mail_once "$_address" "$_subject" "$_body" && return 0
  log "mail send failed; retrying once in ${RETRY_DELAY_SECONDS}s"
  sleep "$RETRY_DELAY_SECONDS"
  send_mail_once "$_address" "$_subject" "$_body"
}

function send_mail_once() {
  "$OSASCRIPT_BIN" - "$1" "$2" "$3" <<'APPLESCRIPT'
on run argv
  set addr to item 1 of argv
  tell application "Mail" to launch
  with timeout of 300 seconds
    tell application "Mail"
      repeat 60 times
        try
          count of accounts
          exit repeat
        on error
          delay 1
        end try
      end repeat
      set hasAccount to false
      repeat with acct in accounts
        if (email addresses of acct) contains addr then set hasAccount to true
      end repeat
      if not hasAccount then error "No Apple Mail account has the address " & addr
      set msg to make new outgoing message with properties {subject:item 2 of argv, content:item 3 of argv, visible:false}
      tell msg
        set sender to addr
        make new to recipient at end of to recipients with properties {address:addr}
        set sent to send
      end tell
      if sent is false then error "Apple Mail failed to send the briefing"
    end tell
  end timeout
end run
APPLESCRIPT
}

# The first line of the report states Claude's coverage; a missing marker counts as partial.
function report_is_complete() {
  [ "$(head -n 1 "$REPORT_FILE")" = "$COVERAGE_COMPLETE" ]
}

function calendar_is_complete() {
  [ -f "$CALENDAR_FILE" ] && [[ "$(<"$CALENDAR_FILE")" == '{"ok":true,'* ]]
}

function deliver_report() {
  local _subject="$SUBJECT"
  if ! report_is_complete || ! calendar_is_complete; then
    _subject="$PARTIAL_SUBJECT"
  fi
  local _body
  _body="$(sed '1{/^coverage: /d;}' "$REPORT_FILE")"
  send_mail "$_subject" "$_body" || {
    log "delivery failed; the report stays at $REPORT_FILE"
    return 1
  }
  log "mailed $_subject"
}

function fail() {
  log "$1"
  send_mail "$FAILURE_SUBJECT" "$1" || true
  exit 1
}

function main() {
  local _force=false
  local _resend=false
  case "${1:-}" in
    --help | -h)
      usage
      exit 0
      ;;
    --force) _force=true ;;
    --resend) _resend=true ;;
    "") ;;
    *)
      usage >&2
      exit 1
      ;;
  esac

  mkdir -p "$STATE_DIR/briefings"
  if [ "$_resend" = true ]; then
    [ -s "$REPORT_FILE" ] || {
      log "no saved report at $REPORT_FILE"
      exit 1
    }
    deliver_report || exit 1
    exit 0
  fi
  if [ "$_force" = false ] && already_started_today; then
    log "skip: a briefing already started on $TODAY"
    exit 0
  fi
  printf '%s\n' "$TODAY" >|"$LAST_RUN_FILE"

  export_calendar

  local _report=""
  if ! _report="$(run_briefing)"; then
    [ -z "$_report" ] || printf '%s\n' "$_report" >|"$REPORT_FILE"
    fail "ブリーフィングの生成に失敗しました．ログ：$LOG_HINT"
  fi
  [ -n "$_report" ] || fail "ブリーフィングが空でした．ログ：$LOG_HINT"
  printf '%s\n' "$_report" >|"$REPORT_FILE"
  log "saved $REPORT_FILE"

  deliver_report || exit 1
}

main "$@"
