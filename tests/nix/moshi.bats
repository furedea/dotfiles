#!/usr/bin/env bats
# Executable specifications for the Nix-managed Moshi host lifecycle.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  MBP_HOME="darwinConfigurations.mbp.config.home-manager.users.kaito"
  MBA_HOME="darwinConfigurations.mba.config.home-manager.users.kaito"
}

@test "Home Manager installs the pinned moshi-hook runtime" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME" --apply '
    config: {
      packages = map
        (package: package.version)
        (builtins.filter (package: (package.pname or "") == "moshi-hook") config.home.packages);
      executable = toString config.home.file.".local/bin/moshi-hook".source;
    }'

  [ "$status" -eq 0 ]
  run jq -e '
    .packages == ["0.3.21"]
      and (.executable | startswith("/nix/store/"))
      and (.executable | endswith("/bin/moshi-hook"))
  ' <<<"$output"
  [ "$status" -eq 0 ]
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

@test "MacBook Pro runs the Nix-managed moshi-hook runtime" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.launchd.agents.moshi-hook.config.EnvironmentVariables"

  [ "$status" -eq 0 ]
  run jq -e '
    (.MOSHI_HOOK_BIN | startswith("/nix/store/"))
      and (.MOSHI_HOOK_BIN | contains("moshi-hook-0.3.21"))
      and (.MOSHI_HOOK_BIN | endswith("/bin/moshi-hook"))
  ' <<<"$output"
  [ "$status" -eq 0 ]
}

@test "MacBook Pro does not run a mutable runtime updater" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.launchd.agents" \
    --apply 'agents: builtins.hasAttr "moshi-hook-updater" agents'

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
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

@test "Moshi does not require Home Manager migration hooks" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$MBP_HOME.home.activation" \
    --apply 'activation: builtins.filter (name: builtins.match "moshi.*" name != null) (builtins.attrNames activation)'

  [ "$status" -eq 0 ]
  [ "$output" = "[]" ]
}
