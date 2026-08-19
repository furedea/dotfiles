#!/usr/bin/env bats
# Executable specifications for restoring SSH signing identities after login.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "login agent loads identities from the macOS Keychain" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#homeConfigurations.kaito.config.launchd.agents.ssh-agent-loader.config.ProgramArguments"

  [ "$status" -eq 0 ]
  [ "$output" = '["/usr/bin/ssh-add","--apple-load-keychain"]' ]
}

@test "identity loader starts when the user logs in" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#homeConfigurations.kaito.config.launchd.agents.ssh-agent-loader.config.RunAtLoad"

  [ "$status" -eq 0 ]
  [ "$output" = "true" ]
}

@test "SSH connections retain newly used identities in the agent" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    --apply 'home: home.config.programs.ssh.matchBlocks."*".data.addKeysToAgent' \
    "$REPO_ROOT#homeConfigurations.kaito"

  [ "$status" -eq 0 ]
  [ "$output" = '"yes"' ]
}

@test "SSH connections retrieve passphrases from the macOS Keychain" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    --apply 'home: home.config.programs.ssh.matchBlocks."*".data.extraOptions.UseKeychain' \
    "$REPO_ROOT#homeConfigurations.kaito"

  [ "$status" -eq 0 ]
  [ "$output" = '"yes"' ]
}
