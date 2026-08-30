#!/usr/bin/env bats
# Executable specifications for the host-scoped Hister service.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "MacBook Pro starts Hister through the authenticated launcher at login" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#darwinConfigurations.mbp.config.launchd.user.agents.hister.serviceConfig"

  [ "$status" -eq 0 ]
  run jq -e '
    .RunAtLoad == true
      and (.ProgramArguments[0] | endswith("/bin/run_hister_server"))
      and (.ProgramArguments[1] | endswith("/bin/hister"))
      and .ProgramArguments[2] == "kaito"
      and .ThrottleInterval == 60
  ' <<<"$output"
  [ "$status" -eq 0 ]
}

@test "MacBook Pro keeps the Hister token out of generated settings" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#darwinConfigurations.mbp.config.services.hister.settings" \
    --apply 'settings: builtins.hasAttr "access_token" (settings.app or { })'

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
}

@test "MacBook Pro keeps credentials out of the Hister LaunchAgent environment" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#darwinConfigurations.mbp.config.launchd.user.agents.hister.serviceConfig.EnvironmentVariables"

  [ "$status" -eq 0 ]
  run jq -e '
    keys
      | all(test("token|password|credential|secret"; "i") | not)
  ' <<<"$output"
  [ "$status" -eq 0 ]
}

@test "MacBook Pro keeps Hister bound to loopback" {
  run --separate-stderr nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#darwinConfigurations.mbp.config.services.hister.settings.server.address"

  [ "$status" -eq 0 ]
  [ "$output" = "127.0.0.1:4433" ]
}

@test "MacBook Pro advertises the Tailscale HTTPS origin" {
  run --separate-stderr nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#darwinConfigurations.mbp.config.services.hister.settings.server.base_url"

  [ "$status" -eq 0 ]
  [ "$output" = "https://mbp.tailbb556b.ts.net" ]
}

@test "MacBook Air does not install a Hister LaunchAgent" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#darwinConfigurations.mba.config.launchd.user.agents" \
    --apply 'agents: builtins.hasAttr "hister" agents'

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
}

@test "MacBook Air installs the Hister client" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#darwinConfigurations.mba.config.home-manager.users.kaito.home.packages" \
    --apply 'packages: builtins.any (package: (package.pname or "") == "hister") packages'

  [ "$status" -eq 0 ]
  [ "$output" = "true" ]
}

@test "MacBook Air directs the Hister client to MacBook Pro" {
  run --separate-stderr nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#darwinConfigurations.mba.config.home-manager.users.kaito.home.file" \
    --apply \
    'files: (builtins.fromJSON (builtins.readFile files."Library/Preferences/hister/config.yml".source)).server.base_url'

  [ "$status" -eq 0 ]
  [ "$output" = "https://mbp.tailbb556b.ts.net" ]
}
