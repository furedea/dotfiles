#!/usr/bin/env bats
# Executable specifications for external agent hook composition.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "rendered hooks use managed Herdr assets and the Nix Moshi runtime" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#homeConfigurations.kaito.activationPackage"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]

  local _generation="$output"
  local _activation="$_generation/activate"
  local _codex_hooks="$_generation/home-files/.codex/hooks.json"
  local _rendered
  _rendered=$(grep -oE '/nix/store/[a-z0-9]+-agent-harness-rendered' "$_activation" | head -n 1)
  local _claude_settings="$_rendered/.claude/settings.json"

  local _entry
  for _entry in .codex/hooks/hook_adapter.py .claude/hooks/guard_command.py \
    .claude/hooks/verification_session.py .claude/statusline/statusline.py; do
    [ -x "$_rendered/$_entry" ]
    head -n 1 "$_rendered/$_entry" | grep -Eq '^#!/nix/store/[^ ]+/bin/env -S /nix/store/[^ ]+/bin/python3[^ ]* -IB$'
  done
  mkdir -p "$BATS_TEST_TMPDIR/empty-path"
  run env PATH="$BATS_TEST_TMPDIR/empty-path" "$_rendered/.claude/statusline/statusline.py" <<<'{}'
  [ "$status" -eq 0 ]
  [[ "$output" == *"Ctx:"* ]]

  [ -f "$_generation/home-files/.codex/hooks/external/herdr/herdr-agent-state.sh" ]
  [ -n "$_rendered" ]
  [ -f "$_rendered/.claude/hooks/external/herdr/herdr-agent-state.sh" ]
  [ ! -e "$_generation/home-files/.claude/settings.json" ]
  grep -Fq 'sync-claude-settings' "$_activation"
  grep -Fq -- "--source $_claude_settings" "$_activation"
  grep -Fq -- "--target \"\$HOME/.claude/settings.json\"" "$_activation"
  cmp "$REPO_ROOT/agents/AGENTS.md" "$_rendered/.claude/CLAUDE.md"
  # shellcheck disable=SC2016
  grep -Fq -- \
    'bash \"$HOME/.codex/hooks/external/herdr/herdr-agent-state.sh\" session' \
    "$_codex_hooks"
  jq -e '
    .hooks.Stop
      | any(.[]; any(.hooks[]; .command == "\"$HOME/.claude/hooks/verification_session.py\" codex stop"))
  ' "$_codex_hooks" >/dev/null
  grep -Eq -- "'/nix/store/[a-z0-9]+-moshi-hook-0\\.3\\.21/bin/moshi-hook' codex-hook" \
    "$_codex_hooks"
  grep -Eq -- "'/nix/store/[a-z0-9]+-moshi-hook-0\\.3\\.21/bin/moshi-hook' claude-hook" \
    "$_claude_settings"
  run ! grep -Fq -- '/opt/homebrew/bin/moshi-hook' "$_codex_hooks"
  run ! grep -Fq -- '/opt/homebrew/bin/moshi-hook' "$_claude_settings"
}

@test "rendered hooks install the Hermes plugin and the pi bridge" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#homeConfigurations.kaito.activationPackage"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]

  local _generation="$output"
  local _activation="$_generation/activate"
  local _rendered
  _rendered=$(grep -oE '/nix/store/[a-z0-9]+-agent-harness-rendered' "$_activation" | head -n 1)

  for _entry in .hermes/hooks/hook_adapter.py .pi/hooks/hook_adapter.py; do
    [ -x "$_rendered/$_entry" ]
    head -n 1 "$_rendered/$_entry" | grep -Eq '^#!/nix/store/[^ ]+/bin/env -S /nix/store/[^ ]+/bin/python3[^ ]* -IB$'
  done
  [ -f "$_rendered/.claude/hooks/lib/hook_dispatch.py" ]

  [ -f "$_generation/home-files/.hermes/hooks.json" ]
  [ -f "$_generation/home-files/.hermes/plugins/agent-harness-hooks/plugin.yaml" ]
  [ -f "$_generation/home-files/.hermes/plugins/agent-harness-hooks/__init__.py" ]
  [ -f "$_generation/home-files/.pi/agent/hooks.json" ]
  [ -f "$_generation/home-files/.pi/agent/extensions/hook_bridge.ts" ]
  grep -Fq 'sync-hermes-config' "$_activation"

  jq -e '
    .hooks.pre_tool_call
      | any(.[]; any(.hooks[]; .command == "\"$HOME/.hermes/hooks/hook_adapter.py\" native pre-tool-use"))
  ' "$_generation/home-files/.hermes/hooks.json" >/dev/null
  jq -e '
    .hooks.tool_call
      | any(.[]; any(.hooks[]; .command == "\"$HOME/.pi/hooks/hook_adapter.py\" native pre-tool-use"))
  ' "$_generation/home-files/.pi/agent/hooks.json" >/dev/null
  jq -e '
    .hooks.input
      | any(.[]; any(.hooks[]; .command == "\"$HOME/.pi/hooks/hook_adapter.py\" content prompt"))
  ' "$_generation/home-files/.pi/agent/hooks.json" >/dev/null
}
