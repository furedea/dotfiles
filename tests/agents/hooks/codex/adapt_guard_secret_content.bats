#!/usr/bin/env bats
# Tests for codex/hooks/adapt_guard_secret_content.sh

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../.." && pwd)"
  HOOK="$REPO_ROOT/agents/codex/hooks/adapt_guard_secret_content.sh"
}

@test "exits non-zero without mode argument" {
  run "$HOOK"
  [ "$status" -ne 0 ]
}

@test "prints usage with --help" {
  run "$HOOK" --help
  [ "$status" -ne 0 ]
  [[ "$output" == *"Usage"* ]]
}

@test "added_patch_text extracts added lines from unified diff" {
  result=$(printf '%s' '--- a/foo.py
+++ b/foo.py
@@ -1 +1 @@
-old
+new_line
+another' | awk '/^\+\+\+/ { next } /^\+/ { print substr($0, 2) }')

  [ "$result" = "$(printf 'new_line\nanother')" ]
}

@test "added_patch_text skips +++ header lines" {
  result=$(printf '%s' '+++ b/foo.py
+actual content' | awk '/^\+\+\+/ { next } /^\+/ { print substr($0, 2) }')

  [ "$result" = "actual content" ]
}

@test "prompt mode delegates to shared scanner" {
  STUB_DIR="$(mktemp -d "$BATS_TEST_TMPDIR/stub.XXXXXX")"
  mkdir -p "$STUB_DIR/.claude/hooks"
  cat >"$STUB_DIR/.claude/hooks/guard_secret_content.sh" <<'STUB'
#!/bin/bash
echo "CALLED:$1"
cat > /dev/null
STUB
  chmod +x "$STUB_DIR/.claude/hooks/guard_secret_content.sh"

  run bash -c "export HOME='$STUB_DIR'; echo '{\"prompt\":\"hello\"}' | '$HOOK' prompt"
  [ "$status" -eq 0 ]
  [[ "$output" == *"CALLED:prompt"* ]]
}

@test "prompt mode resolves the shared scanner from the harness root" {
  local _home
  _home="$(mktemp -d "$BATS_TEST_TMPDIR/home.XXXXXX")"
  local _harness_root
  _harness_root="$(mktemp -d "$BATS_TEST_TMPDIR/harness.XXXXXX")"
  mkdir -p "$_harness_root/.claude/hooks"
  cat >"$_harness_root/.claude/hooks/guard_secret_content.sh" <<'STUB'
#!/usr/bin/env bash
set -euxCo pipefail
cd "$(dirname "$0")"

printf 'CALLED:%s\n' "$1"
cat >/dev/null
STUB
  chmod +x "$_harness_root/.claude/hooks/guard_secret_content.sh"

  run env HOME="$_home" AGENT_HARNESS_ROOT="$_harness_root" \
    bash -c "echo '{\"prompt\":\"hello\"}' | '$HOOK' prompt"

  [ "$status" -eq 0 ]
  [[ "$output" == *"CALLED:prompt"* ]]
}

@test "prompt mode does not emit shell trace when scanner is silent" {
  STUB_DIR="$(mktemp -d "$BATS_TEST_TMPDIR/stub.XXXXXX")"
  mkdir -p "$STUB_DIR/.claude/hooks"
  cat >"$STUB_DIR/.claude/hooks/guard_secret_content.sh" <<'STUB'
#!/bin/bash
cat >/dev/null
STUB
  chmod +x "$STUB_DIR/.claude/hooks/guard_secret_content.sh"

  run bash -c "export HOME='$STUB_DIR'; echo '{\"prompt\":\"hello\"}' | '$HOOK' prompt"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "apply-patch mode delegates to shared scanner with write arg" {
  STUB_DIR="$(mktemp -d "$BATS_TEST_TMPDIR/stub.XXXXXX")"
  mkdir -p "$STUB_DIR/.claude/hooks"
  cat >"$STUB_DIR/.claude/hooks/guard_secret_content.sh" <<'STUB'
#!/bin/bash
echo "CALLED:$1"
cat > /dev/null
STUB
  chmod +x "$STUB_DIR/.claude/hooks/guard_secret_content.sh"

  INPUT='{"tool_input":{"command":"--- a/f\n+++ b/f\n+secret"}}'
  run bash -c "export HOME='$STUB_DIR'; echo '$INPUT' | '$HOOK' apply-patch"
  [ "$status" -eq 0 ]
  [[ "$output" == *"CALLED:write"* ]]
}
