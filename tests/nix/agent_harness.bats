#!/usr/bin/env bats
# Validate that dotfiles delegates agent files to the agent-harness flake module.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOME_NIX="$REPO_ROOT/nix/home/default.nix"
  FLAKE_NIX="$REPO_ROOT/flake.nix"
}

@test "flake imports the agent-harness home-manager module" {
  grep -q 'agent-harness.url = "github:furedea/agent-harness";' "$FLAKE_NIX"
  grep -q 'agent-harness.homeManagerModules.default' "$FLAKE_NIX"
}

@test "home-manager enables agent-harness instead of local generated files" {
  grep -q "agent-harness = {" "$HOME_NIX"
  grep -q "enable = true;" "$HOME_NIX"
  grep -q "package = agent-harness.packages.\${system}.default;" "$HOME_NIX"
  run grep -q 'codex/sync_config.py' "$HOME_NIX"
  [ "$status" -eq 1 ]
  run grep -q 'renderedAgentSkills' "$HOME_NIX"
  [ "$status" -eq 1 ]
  run grep -q '".codex/hooks.json".text' "$HOME_NIX"
  [ "$status" -eq 1 ]
  run grep -q '".claude/settings.json".text' "$HOME_NIX"
  [ "$status" -eq 1 ]
}
