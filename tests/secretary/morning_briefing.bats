#!/usr/bin/env bats
# Executable specifications for the once-a-day morning briefing launcher.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$REPO_ROOT/scripts/secretary/run_morning_briefing.sh"
  TEST_ROOT="$(cd "$BATS_TEST_TMPDIR" && pwd -P)"
  SECRETARY_DIR="$TEST_ROOT/secretary"
  STATE_DIR="$TEST_ROOT/state"
  CLAUDE_LOG="$TEST_ROOT/claude.log"
  OSASCRIPT_LOG="$TEST_ROOT/osascript.log"
  OSASCRIPT_SOURCE="$TEST_ROOT/osascript.source"
  CALENDAR_SOURCE="$TEST_ROOT/calendar.source"
  CALENDAR_ARGS_LOG="$TEST_ROOT/calendar.args"
  mkdir -p "$SECRETARY_DIR" "$STATE_DIR"
  printf 'me@example.test\n' >|"$STATE_DIR/briefing_address"
  create_claude_stub
  create_osascript_stub
}

create_claude_stub() {
  CLAUDE_STUB="$TEST_ROOT/claude"
  cat >|"$CLAUDE_STUB" <<'STUB'
#!/bin/bash
printf '%s|%s\n' "$PWD" "$*" >>"$CLAUDE_LOG"
printf '%s\n' "${BRIEFING_OUTPUT-coverage: complete
# 朝のブリーフィング}"
exit "${BRIEFING_STATUS:-0}"
STUB
  chmod +x "$CLAUDE_STUB"
}

create_osascript_stub() {
  OSASCRIPT_STUB="$TEST_ROOT/osascript"
  cat >|"$OSASCRIPT_STUB" <<'STUB'
#!/bin/bash
if [ "${1:-}" = "-l" ]; then
  printf '%s\n' "$*" >>"$CALENDAR_ARGS_LOG"
  cat >|"$CALENDAR_SOURCE"
  default='{"ok":true,"events":[]}'
  printf '%s\n' "${CALENDAR_OUTPUT-$default}"
  exit "${CALENDAR_STATUS:-0}"
fi
printf 'ARGS: %s\n' "$*" >>"$OSASCRIPT_LOG"
cat >|"$OSASCRIPT_SOURCE"
[ "${OSASCRIPT_STATUS:-0}" -eq 0 ] || exit "$OSASCRIPT_STATUS"
STUB
  chmod +x "$OSASCRIPT_STUB"
}

run_launcher() {
  run --separate-stderr env \
    CLAUDE_BIN="$CLAUDE_STUB" \
    CLAUDE_LOG="$CLAUDE_LOG" \
    OSASCRIPT_BIN="$OSASCRIPT_STUB" \
    OSASCRIPT_LOG="$OSASCRIPT_LOG" \
    OSASCRIPT_SOURCE="$OSASCRIPT_SOURCE" \
    CALENDAR_SOURCE="$CALENDAR_SOURCE" \
    CALENDAR_ARGS_LOG="$CALENDAR_ARGS_LOG" \
    SECRETARY_RETRY_DELAY_SECONDS=0 \
    SECRETARY_DIR="$SECRETARY_DIR" \
    SECRETARY_STATE_DIR="$STATE_DIR" \
    SECRETARY_TODAY=2026-11-05 \
    HOME="$TEST_ROOT/home" \
    "$@" /bin/bash "$SCRIPT" ${LAUNCHER_ARGS:+"$LAUNCHER_ARGS"}
}

@test "a day that already started is skipped without calling claude or Mail" {
  printf '2026-11-05\n' >|"$STATE_DIR/last_run_date"

  run_launcher

  [ "$status" -eq 0 ]
  [ ! -e "$CLAUDE_LOG" ]
  [ ! -e "$OSASCRIPT_LOG" ]
}

@test "--force runs even when the day already started" {
  printf '2026-11-05\n' >|"$STATE_DIR/last_run_date"
  LAUNCHER_ARGS="--force"

  run_launcher

  [ "$status" -eq 0 ]
  [ -s "$STATE_DIR/briefings/2026-11-05.md" ]
}

@test "the briefing runs in the secretary directory with read-only settings" {
  run_launcher

  [ "$status" -eq 0 ]
  local _first
  _first="$(head -n 1 "$CLAUDE_LOG")"
  [[ "$_first" == "$SECRETARY_DIR|"* ]]
  [[ "$_first" == *"--settings $SECRETARY_DIR/.claude/settings.json"* ]]
  [[ "$_first" == *"--permission-mode dontAsk"* ]]
  [[ "$_first" == *"--setting-sources project"* ]]
}

@test "the report is saved by date and the day is recorded" {
  run_launcher

  [ "$status" -eq 0 ]
  [ "$(<"$STATE_DIR/briefings/2026-11-05.md")" = "$(printf 'coverage: complete\n# 朝のブリーフィング')" ]
  [ "$(<"$STATE_DIR/last_run_date")" = "2026-11-05" ]
}

@test "the report is mailed to the briefing address with the dated subject" {
  run_launcher

  [ "$status" -eq 0 ]
  [ "$(wc -l <"$OSASCRIPT_LOG" | tr -d ' ')" = "1" ]
  grep -qF 'ARGS: - me@example.test [briefing] 2026-11-05 # 朝のブリーフィング' "$OSASCRIPT_LOG"
  ! grep -qF 'coverage:' "$OSASCRIPT_LOG"
}

@test "a failed briefing mails a failure notice and keeps any partial output" {
  run_launcher env BRIEFING_STATUS=3 BRIEFING_OUTPUT="partial report"

  [ "$status" -eq 1 ]
  [ "$(<"$STATE_DIR/briefings/2026-11-05.md")" = "partial report" ]
  grep -qF 'ARGS: - me@example.test [briefing] 2026-11-05 失敗 ブリーフィングの生成に失敗しました' "$OSASCRIPT_LOG"
}

@test "a missing address file fails after saving the report" {
  rm "$STATE_DIR/briefing_address"

  run_launcher

  [ "$status" -eq 1 ]
  [ -s "$STATE_DIR/briefings/2026-11-05.md" ]
  [ ! -e "$OSASCRIPT_LOG" ]
  [[ "$output" == *"briefing_address is missing or empty"* ]]
}

@test "the AppleScript raises an error when Mail reports a failed send" {
  run_launcher

  [ "$status" -eq 0 ]
  grep -q 'set sent to send' "$OSASCRIPT_SOURCE"
  grep -q 'if sent is false then error' "$OSASCRIPT_SOURCE"
}

@test "a failed send is retried once, keeps the report and exits non-zero" {
  run_launcher env OSASCRIPT_STATUS=1

  [ "$status" -eq 1 ]
  [ -s "$STATE_DIR/briefings/2026-11-05.md" ]
  [ "$(wc -l <"$OSASCRIPT_LOG" | tr -d ' ')" = "2" ]
  [[ "$output" == *"delivery failed"* ]]
}

@test "the AppleScript launches Mail and waits with an extended timeout" {
  run_launcher

  [ "$status" -eq 0 ]
  grep -q 'launch' "$OSASCRIPT_SOURCE"
  grep -q 'with timeout of 300 seconds' "$OSASCRIPT_SOURCE"
}

@test "today's events are exported through JXA to a dated JSON file" {
  run_launcher env CALENDAR_OUTPUT='{"ok":true,"events":[{"title":"会議"}]}'

  [ "$status" -eq 0 ]
  [ "$(<"$STATE_DIR/calendar/2026-11-05.json")" = '{"ok":true,"events":[{"title":"会議"}]}' ]
  grep -q -- '-l JavaScript' "$CALENDAR_ARGS_LOG"
  grep -q 'EventKit' "$CALENDAR_SOURCE"
  grep -q 'predicateForEventsWithStartDateEndDateCalendars' "$CALENDAR_SOURCE"
}

@test "a failed export records the error and the briefing continues" {
  run_launcher env CALENDAR_STATUS=1 CALENDAR_OUTPUT=""

  [ "$status" -eq 0 ]
  grep -q '^{"ok":false,"error":' "$STATE_DIR/calendar/2026-11-05.json"
  [ -s "$STATE_DIR/briefings/2026-11-05.md" ]
  grep -qF 'ARGS: - me@example.test [briefing] 2026-11-05（一部取得失敗） ' "$OSASCRIPT_LOG"
}

@test "an export that prints invalid JSON is recorded as a failure" {
  run_launcher env CALENDAR_OUTPUT="not json"

  [ "$status" -eq 0 ]
  grep -q '^{"ok":false,"error":' "$STATE_DIR/calendar/2026-11-05.json"
}

@test "the subject is plain when the calendar and mail are both covered" {
  run_launcher

  [ "$status" -eq 0 ]
  grep -qF 'ARGS: - me@example.test [briefing] 2026-11-05 ' "$OSASCRIPT_LOG"
  ! grep -qF '一部取得失敗' "$OSASCRIPT_LOG"
}

@test "a partial coverage marker marks the subject and is stripped from the body" {
  run_launcher env BRIEFING_OUTPUT="$(printf 'coverage: partial\n# 本文')"

  [ "$status" -eq 0 ]
  grep -qF 'ARGS: - me@example.test [briefing] 2026-11-05（一部取得失敗） # 本文' "$OSASCRIPT_LOG"
}

@test "a missing coverage marker is treated as partial" {
  run_launcher env BRIEFING_OUTPUT="# 本文のみ"

  [ "$status" -eq 0 ]
  grep -qF '[briefing] 2026-11-05（一部取得失敗） # 本文のみ' "$OSASCRIPT_LOG"
}

@test "--resend mails the saved report without running claude or the export" {
  mkdir -p "$STATE_DIR/briefings" "$STATE_DIR/calendar"
  printf 'coverage: complete\n# 保存済み\n' >|"$STATE_DIR/briefings/2026-11-05.md"
  printf '{"ok":true,"events":[]}\n' >|"$STATE_DIR/calendar/2026-11-05.json"
  LAUNCHER_ARGS="--resend"

  run_launcher

  [ "$status" -eq 0 ]
  [ ! -e "$CLAUDE_LOG" ]
  [ ! -e "$CALENDAR_ARGS_LOG" ]
  grep -qF 'ARGS: - me@example.test [briefing] 2026-11-05 # 保存済み' "$OSASCRIPT_LOG"
}

@test "--resend uses the saved calendar failure for the subject" {
  mkdir -p "$STATE_DIR/briefings" "$STATE_DIR/calendar"
  printf 'coverage: complete\n# 保存済み\n' >|"$STATE_DIR/briefings/2026-11-05.md"
  printf '{"ok":false,"error":"denied"}\n' >|"$STATE_DIR/calendar/2026-11-05.json"
  LAUNCHER_ARGS="--resend"

  run_launcher

  [ "$status" -eq 0 ]
  grep -qF '[briefing] 2026-11-05（一部取得失敗） # 保存済み' "$OSASCRIPT_LOG"
}

@test "--resend fails when no report was saved today" {
  LAUNCHER_ARGS="--resend"

  run_launcher

  [ "$status" -eq 1 ]
  [ ! -e "$OSASCRIPT_LOG" ]
  [[ "$output" == *"no saved report"* ]]
}

@test "an unknown option is rejected with usage" {
  LAUNCHER_ARGS="--bogus"

  run_launcher

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"Usage:"* ]]
}
