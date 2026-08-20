#!/usr/bin/env bats
# Executable specifications for external agent hook composition.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Home Manager composes Herdr and Moshi hook bundles" {
  run --separate-stderr nix eval --json \
    "$REPO_ROOT#homeConfigurations.kaito.config.programs.agent-harness.hooks.extra" \
    --apply 'hooks: builtins.attrNames hooks'

  [ "$status" -eq 0 ]
  [ "$output" = '["herdr","moshi"]' ]
}

@test "rendered hooks use managed Herdr assets and the Homebrew Moshi runtime" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#homeConfigurations.kaito.activationPackage"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]

  local _generation="$output"
  local _codex_hooks="$_generation/home-files/.codex/hooks.json"
  local _claude_settings="$_generation/home-files/.claude/settings.json"

  [ -f "$_generation/home-files/.codex/hooks/external/herdr/herdr-agent-state.sh" ]
  [ -f "$_generation/home-files/.claude/hooks/external/herdr/herdr-agent-state.sh" ]
  grep -Fq -- \
    'bash \"$HOME/.codex/hooks/external/herdr/herdr-agent-state.sh\" session' \
    "$_codex_hooks"
  grep -Fq -- "'/opt/homebrew/bin/moshi-hook' codex-hook" "$_codex_hooks"
  grep -Fq -- "'/opt/homebrew/bin/moshi-hook' claude-hook" "$_claude_settings"
  ! grep -Fq -- '/nix/store' "$_codex_hooks"
  ! grep -Fq -- '/nix/store' "$_claude_settings"
}
