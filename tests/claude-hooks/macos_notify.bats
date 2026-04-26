#!/usr/bin/env bats
# Tests for .claude/hooks/macos_notify_done.sh and macos_notify_await.sh
#
# These hooks depend on macOS-specific commands (osascript, afplay).
# Tests verify script structure and syntax rather than actual notification behavior.

setup() {
  load test_helper/setup
  DONE_HOOK="$HOOK_DIR/macos_notify_done.sh"
  AWAIT_HOOK="$HOOK_DIR/macos_notify_await.sh"
}

# ============================================================
# File structure
# ============================================================

@test "macos_notify_done.sh exists and is executable" {
  [ -f "$DONE_HOOK" ]
  [ -x "$DONE_HOOK" ]
}

@test "macos_notify_await.sh exists and is executable" {
  [ -f "$AWAIT_HOOK" ]
  [ -x "$AWAIT_HOOK" ]
}

@test "macos_notify_done.sh has set -euCo pipefail" {
  grep -q 'set -euCo pipefail' "$DONE_HOOK"
}

@test "macos_notify_await.sh has set -euCo pipefail" {
  grep -q 'set -euCo pipefail' "$AWAIT_HOOK"
}

@test "macos_notify_done.sh uses osascript" {
  grep -q 'osascript' "$DONE_HOOK"
}

@test "macos_notify_await.sh uses osascript" {
  grep -q 'osascript' "$AWAIT_HOOK"
}

@test "macos_notify_done.sh uses afplay" {
  grep -q 'afplay' "$DONE_HOOK"
}

@test "macos_notify_await.sh uses afplay" {
  grep -q 'afplay' "$AWAIT_HOOK"
}

# ============================================================
# Syntax validation
# ============================================================

@test "macos_notify_done.sh passes bash syntax check" {
  run bash -n "$DONE_HOOK"
  [ "$status" -eq 0 ]
}

@test "macos_notify_await.sh passes bash syntax check" {
  run bash -n "$AWAIT_HOOK"
  [ "$status" -eq 0 ]
}

# ============================================================
# Sound file references
# ============================================================

@test "macos_notify_done.sh references a system sound file" {
  grep -qE '/System/Library/Sounds/.*\.aiff' "$DONE_HOOK"
}

@test "macos_notify_await.sh references a system sound file" {
  grep -qE '/System/Library/Sounds/.*\.aiff' "$AWAIT_HOOK"
}

@test "done and await use different notification sounds" {
  local done_sound await_sound
  done_sound=$(grep -oE '/System/Library/Sounds/[^"]+' "$DONE_HOOK")
  await_sound=$(grep -oE '/System/Library/Sounds/[^"]+' "$AWAIT_HOOK")
  [ "$done_sound" != "$await_sound" ]
}

@test "done and await use different notification messages" {
  local done_msg await_msg
  done_msg=$(grep -o 'display notification "[^"]*"' "$DONE_HOOK")
  await_msg=$(grep -o 'display notification "[^"]*"' "$AWAIT_HOOK")
  [ "$done_msg" != "$await_msg" ]
}
