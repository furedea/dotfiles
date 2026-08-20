#!/usr/bin/env bats
# Executable specifications for restoring SSH signing identities after login.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

evaluate_ssh_identity_check() {
  nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.activation.sshIdentityCheck.data"
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

@test "home activation leaves SSH identity creation to the user" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    --apply 'home: builtins.hasAttr "sshKeyGen" home.config.home.activation' \
    "$REPO_ROOT#homeConfigurations.kaito"

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
}

@test "home activation reports a missing SSH identity" {
  run --separate-stderr evaluate_ssh_identity_check

  [ "$status" -eq 0 ]
  activation_script="$output"

  run env HOME="$BATS_TEST_TMPDIR/home" /bin/bash -c "$activation_script"

  [ "$status" -eq 0 ]
  [[ "$output" == *"SSH identity is missing."* ]]
}

@test "home activation stays quiet when the SSH identity exists" {
  run --separate-stderr evaluate_ssh_identity_check

  [ "$status" -eq 0 ]
  activation_script="$output"
  mkdir -p "$BATS_TEST_TMPDIR/home/.ssh"
  touch "$BATS_TEST_TMPDIR/home/.ssh/id_ed25519"

  run env HOME="$BATS_TEST_TMPDIR/home" /bin/bash -c "$activation_script"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
