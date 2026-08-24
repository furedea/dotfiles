#!/usr/bin/env bats
# Executable specifications for Herdr popup commands.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Herdr uses a fixed dark Catppuccin theme" {
  run --separate-stderr nix eval --impure --json --expr "
    let
      config = builtins.fromTOML (builtins.readFile \"$REPO_ROOT/herdr/config.toml\");
    in
    config.theme.name == \"catppuccin\" && !config.theme.auto_switch
  "

  [ "$status" -eq 0 ]
  [ "$output" = "true" ]
}

@test "Nix popup tools resolve without the Herdr server PATH" {
  run --separate-stderr nix eval --impure --json --expr "
    let
      config = builtins.fromTOML (builtins.readFile \"$REPO_ROOT/herdr/config.toml\");
      commandFor = description:
        (builtins.head (builtins.filter
          (item: item.description == description)
          config.keys.command)).command;
      commands = map commandFor [ \"run yazi\" \"run lazygit\" ];
    in
    builtins.all
      (command: builtins.substring 0 1 command == \"/\" && builtins.pathExists command)
      commands
  "

  [ "$status" -eq 0 ]
  [ "$output" = "true" ]
}
