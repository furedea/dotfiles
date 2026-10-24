#!/usr/bin/env bats
# Executable specifications for external agent hook composition.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "rendered hooks use managed Herdr assets and the Nix Moshi runtime" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#homeConfigurations.\"kaito@mbp\".activationPackage"

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

  [ -f "$_generation/home-files/.codex/hooks/external/herdr/herdr-agent-state.sh" ]
  [ -n "$_rendered" ]
  [ -f "$_rendered/.claude/hooks/external/herdr/herdr-agent-state.sh" ]
  [ ! -e "$_generation/home-files/.claude/settings.json" ]
  grep -Fq 'sync-claude-settings' "$_activation"
  grep -Fq -- "--source $_claude_settings" "$_activation"
  grep -Fq -- "--target \"\$HOME/.claude/settings.json\"" "$_activation"
  local _source
  _source=$(nix build --no-link --print-out-paths --inputs-from "$REPO_ROOT" agent-config#default)
  cmp "$_source/AGENTS.md" "$_rendered/.claude/CLAUDE.md"
  # shellcheck disable=SC2016
  grep -Fq -- \
    'bash \"$HOME/.codex/hooks/external/herdr/herdr-agent-state.sh\" session' \
    "$_codex_hooks"
  jq -e '
    .hooks.Stop
      | any(.[]; any(.hooks[]; .command == "\"$HOME/.claude/hooks/verification_session.py\" codex stop"))
  ' "$_codex_hooks" >/dev/null
  local _moshi_version
  _moshi_version=$(sed -n 's/^  version = "\([0-9.]*\)";$/\1/p' "$REPO_ROOT/nix/packages/moshi_hook.nix")
  [[ "$_moshi_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
  local _moshi_runtime="/nix/store/[a-z0-9]+-moshi-hook-${_moshi_version//./\\.}/bin/moshi-hook"
  grep -Eq -- "'$_moshi_runtime' codex-hook" "$_codex_hooks"
  grep -Eq -- "'$_moshi_runtime' claude-hook" "$_claude_settings"
  run ! grep -Fq -- '/opt/homebrew/bin/moshi-hook' "$_codex_hooks"
  run ! grep -Fq -- '/opt/homebrew/bin/moshi-hook' "$_claude_settings"
}

@test "rendered agents deploy the dotfiles-owned nix-dotfiles skill" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#homeConfigurations.\"kaito@mbp\".activationPackage"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]

  local _generation="$output"
  local _agent
  for _agent in .claude .codex; do
    cmp "$REPO_ROOT/skills/nix-dotfiles/SKILL.md" \
      "$_generation/home-files/$_agent/skills/nix-dotfiles/SKILL.md"
  done
}
