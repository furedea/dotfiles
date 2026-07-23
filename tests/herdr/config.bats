#!/usr/bin/env bats
# Tests for Herdr configuration.

setup() {
  load test-helper/setup
  CONFIG="$REPO_ROOT/herdr/config.toml"
}

@test "opens terminal tools in 85 percent popup panes" {
  run nix eval --impure --json --expr "builtins.fromTOML (builtins.readFile $CONFIG)"

  [ "$status" -eq 0 ]
  config_json="$output"

  run jq -e '
    .keys.command == [
      {
        "key": "prefix+ctrl+y",
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
      }
    ]
  ' <<<"$config_json"

  [ "$status" -eq 0 ]
}
