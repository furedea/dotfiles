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
  mkdir -p "$SECRETARY_DIR"
  create_claude_stub
  create_osascript_stub
}

create_claude_stub() {
  CLAUDE_STUB="$TEST_ROOT/claude"
  cat >|"$CLAUDE_STUB" <<'EOF'
#!/bin/bash
printf '%s|%s\n' "$PWD" "$*" >>"$CLAUDE_LOG"
case "$*" in
  *publish.settings.json*)
    [ "${PUBLISH_STATUS:-0}" -eq 0 ] || exit "$PUBLISH_STATUS"
    printf '%s\n' "${PUBLISH_OUTPUT:-ARTIFACT_URL=https://claude.ai/artifact/abc}"
    ;;
  *)
    [ "${BRIEFING_STATUS:-0}" -eq 0 ] || exit "$BRIEFING_STATUS"
    printf '%s\n' "${BRIEFING_OUTPUT:-# 朝のブリーフィング}"
    ;;
esac
EOF
  chmod +x "$CLAUDE_STUB"
}

create_osascript_stub() {
  OSASCRIPT_STUB="$TEST_ROOT/osascript"
  cat >|"$OSASCRIPT_STUB" <<'EOF'
#!/bin/bash
printf 'ARGS: %s\n' "$*" >>"$OSASCRIPT_LOG"
if grep -q 'make new reminder' -; then
  printf 'KIND: create\n' >>"$OSASCRIPT_LOG"
else
  printf 'KIND: complete\n' >>"$OSASCRIPT_LOG"
fi
EOF
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

@test "a day that already started is skipped without calling claude" {
  mkdir -p "$STATE_DIR"
  printf '2026-11-05\n' >|"$STATE_DIR/last_run_date"

  run_launcher

  [ "$status" -eq 0 ]
  [ ! -e "$CLAUDE_LOG" ]
  [ ! -e "$OSASCRIPT_LOG" ]
}

@test "--force runs even when the day already started" {
  mkdir -p "$STATE_DIR"
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
}

@test "the report is saved by date and the day is recorded" {
  run_launcher

  [ "$status" -eq 0 ]
  [ "$(<"$STATE_DIR/briefings/2026-11-05.md")" = "# 朝のブリーフィング" ]
  [ "$(<"$STATE_DIR/last_run_date")" = "2026-11-05" ]
}

@test "publishing stores the Artifact URL and puts it in the reminder" {
  run_launcher

  [ "$status" -eq 0 ]
  [ "$(<"$STATE_DIR/artifact_url")" = "https://claude.ai/artifact/abc" ]
  grep -q 'ARGS: - 朝のブリーフィング 2026-11-05 https://claude.ai/artifact/abc' "$OSASCRIPT_LOG"
}

@test "a known Artifact URL is updated in place" {
  mkdir -p "$STATE_DIR"
  printf 'https://claude.ai/artifact/known\n' >|"$STATE_DIR/artifact_url"

  run_launcher

  [ "$status" -eq 0 ]
  grep -q 'Update the existing Artifact https://claude.ai/artifact/known' "$CLAUDE_LOG"
}

@test "publishing runs outside the secretary directory with its own settings" {
  run_launcher

  grep -q "^$STATE_DIR/artifact|" "$CLAUDE_LOG"
  grep -q -- "--settings $SECRETARY_DIR/publish.settings.json" "$CLAUDE_LOG"
}

@test "previous reminders are completed before the new one is created" {
  run_launcher

  [ "$status" -eq 0 ]
  [ "$(grep '^KIND:' "$OSASCRIPT_LOG" | tr '\n' ' ')" = "KIND: complete KIND: create " ]
  grep -q 'ARGS: - 朝のブリーフィング$' "$OSASCRIPT_LOG"
}

@test "a failed briefing notifies the failure and saves nothing" {
  run_launcher env BRIEFING_STATUS=3

  [ "$status" -eq 1 ]
  [ ! -e "$STATE_DIR/briefings/2026-11-05.md" ]
  grep -q 'ARGS: - 朝のブリーフィング 2026-11-05 ブリーフィングの生成に失敗しました' "$OSASCRIPT_LOG"
}

@test "a failed publish keeps the local report and notifies the failure" {
  run_launcher env PUBLISH_STATUS=1

  [ "$status" -eq 1 ]
  [ -s "$STATE_DIR/briefings/2026-11-05.md" ]
  [ ! -e "$STATE_DIR/artifact_url" ]
  grep -q "Artifact の公開に失敗しました．ローカル保存: $STATE_DIR/briefings/2026-11-05.md" "$OSASCRIPT_LOG"
}

@test "an unknown option is rejected with usage" {
  LAUNCHER_ARGS="--bogus"

  run_launcher

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"Usage:"* ]]
}
