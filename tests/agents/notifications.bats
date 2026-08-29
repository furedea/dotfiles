#!/usr/bin/env bats
# Official notification settings replace local macOS notification hooks.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  CLAUDE_SETTINGS="$REPO_ROOT/agents/claude/settings.base.json"
  CODEX_CONFIG="$REPO_ROOT/agents/codex/config.toml"
  HOOKS="$REPO_ROOT/agents/hooks.json"
}

@test "Claude uses the official automatic notification channel" {
  [ "$(jq -r '.preferredNotifChannel' "$CLAUDE_SETTINGS")" = "auto" ]
}

@test "Codex notifies for completion and approval only while unfocused" {
  grep -Fqx 'notifications = ["agent-turn-complete", "approval-requested"]' "$CODEX_CONFIG"
  grep -Fqx 'notification_condition = "unfocused"' "$CODEX_CONFIG"
  grep -Fqx 'notification_method = "auto"' "$CODEX_CONFIG"
}

@test "provider hooks do not register local macOS notifications" {
  ! grep -Fq 'notify_macos_' "$HOOKS"
  jq -e '.claude.hooks | has("Notification") | not' "$HOOKS" >/dev/null
  jq -e '.claude.hooks | has("SubagentStop") | not' "$HOOKS" >/dev/null
}

@test "related tests remain the only Claude Stop hook" {
  [ "$(jq -r '.claude.hooks.Stop[0].hooks | length' "$HOOKS")" -eq 1 ]
  [ "$(jq -r '.claude.hooks.Stop[0].hooks[0].command' "$HOOKS")" = \
    '$HOME/.claude/hooks/run_related_tests.sh' ]
}
