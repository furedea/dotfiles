#!/usr/bin/env bats
# Tests for codex/hooks/adapt_harness_files.sh

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../.." && pwd)"
  HOOK="$REPO_ROOT/agents/codex/hooks/adapt_harness_files.sh"
}

install_shared_hook() {
  local _home="$1"

  mkdir -p "$_home/.claude/hooks/lib" "$_home/.claude/hooks/rules"
  cp "$REPO_ROOT/agents/hooks/guard_harness_files.sh" "$_home/.claude/hooks/"
  cp "$REPO_ROOT/agents/hooks/lib/audit_log.sh" "$_home/.claude/hooks/lib/"
  jq -n '{version:1,paths:["~/.codex/hooks/adapt_shell_command.sh"]}' \
    >"$_home/.claude/hooks/rules/protected_paths.json"
  chmod +x "$_home/.claude/hooks/guard_harness_files.sh"
}

@test "prints usage with --help" {
  run "$HOOK" --help
  [ "$status" -ne 0 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "allows Codex apply_patch to harness hook source path" {
  local _tmp
  _tmp="$(mktemp -d "$BATS_TEST_TMPDIR/codex.XXXXXX")"
  install_shared_hook "$_tmp"

  local _patch
  _patch='*** Begin Patch
*** Update File: agents/hooks/guard_allowed_commands.sh
@@
-#!/bin/bash
+#!/bin/bash
*** End Patch'

  local _input
  _input="$(jq -n --arg cwd "$REPO_ROOT" --arg command "$_patch" \
    '{cwd:$cwd,tool_input:{command:$command},session_id:"sess-codex"}')"

  run env HOME="$_tmp" CLAUDE_PROJECT_DIR="$_tmp" bash -c "printf '%s' '$_input' | '$HOOK'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "blocks Codex apply_patch when any generated harness file is protected" {
  local _tmp
  _tmp="$(mktemp -d "$BATS_TEST_TMPDIR/codex.XXXXXX")"
  install_shared_hook "$_tmp"

  local _patch
  _patch="*** Begin Patch
*** Update File: src/app.py
@@
-old
+new
*** Update File: $_tmp/.codex/hooks/adapt_shell_command.sh
@@
-#!/bin/bash
+#!/bin/bash
*** End Patch"

  local _input
  _input="$(jq -n --arg cwd "$REPO_ROOT" --arg command "$_patch" \
    '{cwd:$cwd,tool_input:{command:$command},session_id:"sess-codex"}')"

  run env HOME="$_tmp" CLAUDE_PROJECT_DIR="$_tmp" bash -c "printf '%s' '$_input' | '$HOOK'"
  [ "$status" -eq 2 ]
  [[ "$output" == *"$_tmp/.codex/hooks/adapt_shell_command.sh"* ]]
}

@test "allows Codex apply_patch to normal project files" {
  local _tmp
  _tmp="$(mktemp -d "$BATS_TEST_TMPDIR/codex.XXXXXX")"
  install_shared_hook "$_tmp"

  local _patch
  _patch='*** Begin Patch
*** Update File: src/app.py
@@
-old
+new
*** End Patch'

  local _input
  _input="$(jq -n --arg cwd "$REPO_ROOT" --arg command "$_patch" \
    '{cwd:$cwd,tool_input:{command:$command},session_id:"sess-codex"}')"

  run env HOME="$_tmp" CLAUDE_PROJECT_DIR="$_tmp" bash -c "printf '%s' '$_input' | '$HOOK'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "resolves the shared hook from the harness root" {
  local _home
  _home="$(mktemp -d "$BATS_TEST_TMPDIR/home.XXXXXX")"
  local _harness_root
  _harness_root="$(mktemp -d "$BATS_TEST_TMPDIR/harness.XXXXXX")"
  install_shared_hook "$_harness_root"

  local _input
  _input="$(jq -n --arg cwd "$REPO_ROOT" \
    '{cwd:$cwd,tool_input:{command:"*** Update File: src/app.py"},session_id:"sess-codex"}')"

  run env HOME="$_home" AGENT_HARNESS_ROOT="$_harness_root" \
    CLAUDE_PROJECT_DIR="$_home" bash -c "printf '%s' '$_input' | '$HOOK'"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "blocks when shared hook is missing" {
  local _tmp
  _tmp="$(mktemp -d "$BATS_TEST_TMPDIR/codex.XXXXXX")"
  mkdir -p "$_tmp/.claude/hooks"

  local _input
  _input='{"tool_input":{"command":"*** Update File: src/app.py"}}'

  run env HOME="$_tmp" bash -c "printf '%s' '$_input' | '$HOOK'"
  [ "$status" -eq 2 ]
  [[ "$output" == *"BLOCKED"* ]]
}
