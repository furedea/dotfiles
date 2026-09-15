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

evaluate_ssh_directory_permissions() {
  nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.activation.sshDirectoryPermissions.data"
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

@test "home manager leaves the SSH client config unmanaged" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    --apply 'home: builtins.hasAttr ".ssh/config" home.config.home.file' \
    "$REPO_ROOT#homeConfigurations.kaito"

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
}

@test "home activation leaves SSH identity creation to the user" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    --apply 'home: builtins.hasAttr "sshKeyGen" home.config.home.activation' \
    "$REPO_ROOT#homeConfigurations.kaito"

  [ "$status" -eq 0 ]
  [ "$output" = "false" ]
}

@test "home activation restricts the SSH directory to its owner" {
  run --separate-stderr evaluate_ssh_directory_permissions

  [ "$status" -eq 0 ]
  activation_script="$output"
  mkdir -p "$BATS_TEST_TMPDIR/home/.ssh"
  touch "$BATS_TEST_TMPDIR/home/.ssh/existing-file"
  chmod 0755 "$BATS_TEST_TMPDIR/home/.ssh"

  run env HOME="$BATS_TEST_TMPDIR/home" /bin/bash -c "$activation_script"

  [ "$status" -eq 0 ]
  [ -f "$BATS_TEST_TMPDIR/home/.ssh/existing-file" ]

  run /usr/bin/stat -f "%Lp" "$BATS_TEST_TMPDIR/home/.ssh"

  [ "$status" -eq 0 ]
  [ "$output" = "700" ]
}

@test "home activation reports a missing SSH identity" {
  run --separate-stderr evaluate_ssh_identity_check

  [ "$status" -eq 0 ]
  activation_script="$output"

  run env HOME="$BATS_TEST_TMPDIR/home" /bin/bash -c "$activation_script"

  [ "$status" -eq 0 ]
  [[ "$output" == *"SSH identity is missing."* ]]
}

@test "home activation reports an SSH identity without a passphrase" {
  run --separate-stderr evaluate_ssh_identity_check

  [ "$status" -eq 0 ]
  activation_script="$output"
  mkdir -p "$BATS_TEST_TMPDIR/home/.ssh"
  /usr/bin/ssh-keygen -q -t ed25519 -N "" \
    -f "$BATS_TEST_TMPDIR/home/.ssh/id_ed25519"

  run env HOME="$BATS_TEST_TMPDIR/home" /bin/bash -c "$activation_script"

  [ "$status" -eq 0 ]
  [[ "$output" == *"SSH identity has no passphrase."* ]]
}

@test "home activation stays quiet for a passphrase-protected SSH identity" {
  run --separate-stderr evaluate_ssh_identity_check

  [ "$status" -eq 0 ]
  activation_script="$output"
  mkdir -p "$BATS_TEST_TMPDIR/home/.ssh"
  /usr/bin/ssh-keygen -q -t ed25519 -N "test-passphrase" \
    -f "$BATS_TEST_TMPDIR/home/.ssh/id_ed25519"

  run env HOME="$BATS_TEST_TMPDIR/home" /bin/bash -c "$activation_script"

  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
