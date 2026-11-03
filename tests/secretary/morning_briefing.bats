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
[ "${BRIEFING_STATUS:-0}" -eq 0 ] || exit "$BRIEFING_STATUS"
printf '%s\n' "${BRIEFING_OUTPUT:-# 朝のブリーフィング}"
STUB
  chmod +x "$CLAUDE_STUB"
}

create_osascript_stub() {
  OSASCRIPT_STUB="$TEST_ROOT/osascript"
  cat >|"$OSASCRIPT_STUB" <<'STUB'
#!/bin/bash
[ "${OSASCRIPT_STATUS:-0}" -eq 0 ] || exit "$OSASCRIPT_STATUS"
printf 'ARGS: %s\n' "$*" >>"$OSASCRIPT_LOG"
STUB
  chmod +x "$OSASCRIPT_STUB"
}

run_launcher() {
  run --separate-stderr env \
    CLAUDE_BIN="$CLAUDE_STUB" \
    CLAUDE_LOG="$CLAUDE_LOG" \
    OSASCRIPT_BIN="$OSASCRIPT_STUB" \
    OSASCRIPT_LOG="$OSASCRIPT_LOG" \
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
  [ "$(<"$STATE_DIR/briefings/2026-11-05.md")" = "# 朝のブリーフィング" ]
  [ "$(<"$STATE_DIR/last_run_date")" = "2026-11-05" ]
}

@test "the report is mailed to the briefing address with the dated subject" {
  run_launcher

  [ "$status" -eq 0 ]
  [ "$(wc -l <"$OSASCRIPT_LOG" | tr -d ' ')" = "1" ]
  grep -qF 'ARGS: - me@example.test [briefing] 2026-11-05 # 朝のブリーフィング' "$OSASCRIPT_LOG"
}

@test "a failed briefing mails a failure notice and still exits non-zero" {
  run_launcher env BRIEFING_STATUS=3

  [ "$status" -eq 1 ]
  [ ! -e "$STATE_DIR/briefings/2026-11-05.md" ]
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

@test "a failed send keeps the report and exits non-zero" {
  run_launcher env OSASCRIPT_STATUS=1

  [ "$status" -eq 1 ]
  [ -s "$STATE_DIR/briefings/2026-11-05.md" ]
  [[ "$output" == *"delivery failed"* ]]
}

@test "an unknown option is rejected with usage" {
  LAUNCHER_ARGS="--bogus"

  run_launcher

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"Usage:"* ]]
}
