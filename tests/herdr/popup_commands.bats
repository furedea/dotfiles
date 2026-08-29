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

@test "Herdr shows semantic state text in Agent rows" {
  run --separate-stderr nix eval --impure --json --expr "
    let
      config = builtins.fromTOML (builtins.readFile \"$REPO_ROOT/herdr/config.toml\");
      rows = config.ui.sidebar.agents.rows or [];
    in
    builtins.any
      (row: builtins.elem \"state_text\" row)
      rows
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

@test "Herdr opens the terminal browser in a right split with prefix+ctrl+e" {
  run --separate-stderr nix eval --impure --json --expr "
    let
      config = builtins.fromTOML (builtins.readFile \"$REPO_ROOT/herdr/config.toml\");
      browser = builtins.head (builtins.filter
        (item: item.description == \"open terminal browser\")
        config.keys.command);
      expectedCommand =
        \"HERDR_PANE_ID=\\\"\$HERDR_ACTIVE_PANE_ID\\\" \"
        + \"HERDR_TAB_ID=\\\"\$HERDR_ACTIVE_TAB_ID\\\" \"
        + \"/etc/profiles/per-user/kaito/bin/terminal-browser --split right\";
    in
    browser.key == \"prefix+ctrl+e\"
      && browser.type == \"shell\"
      && browser.command == expectedCommand
  "

  [ "$status" -eq 0 ]
  [ "$output" = "true" ]
}

@test "reviewr starts with branch changes" {
  run --separate-stderr nix eval --impure --json --expr "
    let
      config = builtins.fromTOML (builtins.readFile \"$REPO_ROOT/herdr/reviewr.toml\");
    in
    config.default_scope == \"branch\"
  "

  [ "$status" -eq 0 ]
  [ "$output" = "true" ]
}

@test "Herdr queues the current PR for squash auto-merge in a standard popup" {
  run --separate-stderr nix eval --impure --json --expr "
    let
      config = builtins.fromTOML (builtins.readFile \"$REPO_ROOT/herdr/config.toml\");
      merge = builtins.head (builtins.filter
        (item: item.description == \"queue current PR for squash auto-merge\")
        config.keys.command);
    in
    merge.key == \"prefix+ctrl+p\"
      && merge.type == \"popup\"
      && merge.width == \"85%\"
      && merge.height == \"85%\"
      && builtins.substring 0 27 merge.command == \"gh pr merge --auto --squash\"
  "

  [ "$status" -eq 0 ]
  [ "$output" = "true" ]
}
