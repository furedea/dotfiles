#!/usr/bin/env bats
# Tests for Herdr configuration.

setup() {
  load test-helper/setup
  CONFIG="$REPO_ROOT/herdr/config.toml"
  REVIEWR_CONFIG="$REPO_ROOT/herdr/reviewr.toml"
}

@test "switches workspaces by prefix control number" {
  run nix eval --impure --json --expr "builtins.fromTOML (builtins.readFile $CONFIG)"

  [ "$status" -eq 0 ]

  run jq -e '.keys.switch_workspace == "prefix+ctrl+1..9"' <<<"$output"

  [ "$status" -eq 0 ]
}

@test "uses control bindings for workspace lifecycle actions" {
  run nix eval --impure --json --expr "builtins.fromTOML (builtins.readFile $CONFIG)"

  [ "$status" -eq 0 ]

  run jq -e '
    .keys | {
      new_workspace,
      new_worktree,
      close_workspace
    } == {
      "new_workspace": "prefix+ctrl+n",
      "new_worktree": "prefix+ctrl+w",
      "close_workspace": "prefix+ctrl+d"
    }
  ' <<<"$output"

  [ "$status" -eq 0 ]
}

@test "opens terminal tools in 85 percent popup panes" {
  run nix eval --impure --json --expr "builtins.fromTOML (builtins.readFile $CONFIG)"

  [ "$status" -eq 0 ]
  config_json="$output"

  run jq -e '
    .keys.command == [
      {
        "key": "prefix+ctrl+f",
        "type": "popup",
        "command": "yazi",
        "description": "run yazi",
        "width": "85%",
        "height": "85%"
      },
      {
        "key": "prefix+ctrl+g",
        "type": "popup",
        "command": "lazygit",
        "description": "run lazygit",
        "width": "85%",
        "height": "85%"
      },
      {
        "key": "prefix+ctrl+t",
        "type": "popup",
        "command": "exec zsh",
        "description": "open scratch terminal",
        "width": "85%",
        "height": "85%"
      },
      {
        "key": "prefix+ctrl+r",
        "type": "plugin_action",
        "command": "persiyanov.reviewr.toggle",
        "description": "toggle reviewr"
      }
    ]
  ' <<<"$config_json"

  [ "$status" -eq 0 ]
}

@test "configures reviewr for an on-demand right split" {
  run nix eval --impure --json --expr "builtins.fromTOML (builtins.readFile $REVIEWR_CONFIG)"

  [ "$status" -eq 0 ]

  run jq -e '
    . == {
      "theme": "catppuccin",
      "default_scope": "uncommitted",
      "navigator_position": "right",
      "toggle_placement": "split",
      "toggle_direction": "right",
      "auto_open": false
    }
  ' <<<"$output"

  [ "$status" -eq 0 ]
}
