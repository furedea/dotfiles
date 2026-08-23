#!/usr/bin/env bats
# Executable specifications for the Nix-managed Moshi host lifecycle.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  MBP_HOME="darwinConfigurations.mbp.config.home-manager.users.kaito"
  MBA_HOME="darwinConfigurations.mba.config.home-manager.users.kaito"
}

@test "MacBook Pro runs moshi-hook only in the Aqua user session" {
  run --separate-stderr nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#$MBP_HOME.launchd.agents.moshi-hook.config.LimitLoadToSessionType"

  [ "$status" -eq 0 ]
  [ "$output" = "Aqua" ]
}

@test "MacBook Pro gates the host service on Keychain pairing" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.launchd.agents.moshi-hook.config.ProgramArguments"

  [ "$status" -eq 0 ]
  local _program_arguments="$output"
  run jq -e '.[0] | endswith("/bin/manage_moshi_hook")' \
    <<<"$_program_arguments"
  [ "$status" -eq 0 ]
  run jq -e '.[1:] == ["serve"]' <<<"$_program_arguments"
  [ "$status" -eq 0 ]
}

@test "MacBook Pro keeps the moshi-hook host service available" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.launchd.agents.moshi-hook.config.KeepAlive"

  [ "$status" -eq 0 ]
  [ "$output" = "true" ]
}

@test "MacBook Pro restarts moshi-hook after formula updates in the Aqua session" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.launchd.agents.moshi-hook-updater.config"

  [ "$status" -eq 0 ]
  local _updater_config="$output"
  run jq -e '
    .LimitLoadToSessionType == "Aqua"
      and .WatchPaths == ["/opt/homebrew/Cellar/moshi-hook"]
      and (.ProgramArguments[0] | endswith("/bin/manage_moshi_hook"))
      and .ProgramArguments[1:] == ["restart-after-update"]
  ' <<<"$_updater_config"
  [ "$status" -eq 0 ]
}

@test "formula update helper is dormant until the formula changes" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.launchd.agents.moshi-hook-updater.config"

  [ "$status" -eq 0 ]
  run jq -e '
    (.RunAtLoad // false) == false
      and (.KeepAlive // false) == false
  ' <<<"$output"
  [ "$status" -eq 0 ]
}

@test "Moshi LaunchAgents do not receive credentials through their environment" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.launchd.agents.moshi-hook.config.EnvironmentVariables"

  [ "$status" -eq 0 ]
  run jq -e '
    keys
      | all(test("token|password|credential|secret"; "i") | not)
  ' <<<"$output"
  [ "$status" -eq 0 ]
}

@test "MacBook Air does not run Moshi host LaunchAgents" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBA_HOME.launchd.agents" \
    --apply 'agents: builtins.filter (name: builtins.match "moshi-hook.*" name != null) (builtins.attrNames agents)'

  [ "$status" -eq 0 ]
  [ "$output" = "[]" ]
}

@test "MacBook Air does not migrate a Moshi host service" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBA_HOME.home.activation" \
    --apply 'activation: builtins.filter (name: builtins.match "moshi.*" name != null) (builtins.attrNames activation)'

  [ "$status" -eq 0 ]
  [ "$output" = "[]" ]
}

@test "MacBook Pro activation does not inspect Keychain or daemon state" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.home.activation" \
    --apply \
    'activation: builtins.filter
      (name: builtins.match "moshi.*Check" name != null)
      (builtins.attrNames activation)'

  [ "$status" -eq 0 ]
  [ "$output" = "[]" ]
}

@test "MacBook Pro replaces the legacy service before loading LaunchAgents" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.home.activation.moshiHomebrewServiceMigration"

  [ "$status" -eq 0 ]
  local _migration="$output"
  run jq -e '
    .after == ["writeBoundary"]
      and .before == ["setupLaunchAgents"]
      and (.data | contains("migrate-homebrew-service"))
  ' <<<"$_migration"
  [ "$status" -eq 0 ]
}
