#!/usr/bin/env bats
# Executable specifications for deploying the agent harness on servers without Nix.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/scripts/agents/install_server.sh"
  create_install_server_fixtures
}

# ============================================================
# Tool installation
# ============================================================

@test "installs the pinned user-space tools into the binary directory" {
  run install_server

  [ "$status" -eq 0 ]
  local _tool
  for _tool in agent-harness shfmt rg jq uv; do
    [ -x "$BIN_DIR/$_tool" ] || {
      echo "missing tool: $_tool"
      return 1
    }
  done
}

@test "reuses installed tools without downloading again" {
  run install_server
  [ "$status" -eq 0 ]

  run install_server \
    AGENT_HARNESS_URL="file://$RELEASES/missing.tar.xz" \
    SHFMT_URL="file://$RELEASES/missing" \
    RIPGREP_URL="file://$RELEASES/missing.tar.gz" \
    JQ_URL="file://$RELEASES/missing" \
    UV_INSTALLER_URL="file://$RELEASES/missing.sh"

  [ "$status" -eq 0 ]
}

@test "installs the requested Python through uv" {
  run install_server PYTHON_VERSION=3.15

  [ "$status" -eq 0 ]
  run /bin/cat "$UV_ARGS_FILE"
  [ "${lines[0]}" = "python install 3.15" ]
  [[ "$output" == *"python find"*"3.15"* ]]
}

@test "refuses machines without release binaries before downloading anything" {
  run install_server INSTALL_SERVER_MACHINE=aarch64

  [ "$status" -ne 0 ]
  [[ "$output" == *"aarch64"* ]]
  [[ "$output" == *"cargo install"* ]]
  [ ! -e "$BIN_DIR" ]
}

# ============================================================
# Harness rendering
# ============================================================

@test "renders the repository harness into the home directory and verifies it" {
  run install_server

  [ "$status" -eq 0 ]
  run /bin/cat "$AGENT_HARNESS_ARGS_FILE"
  [[ "$output" == *"install --source $REPO_ROOT/agents --prefix $HOME_DIR"* ]]
  [[ "$output" == *"verify --source $REPO_ROOT/agents --prefix $HOME_DIR"* ]]
}

@test "pins hook shebangs to the managed interpreter" {
  run install_server

  [ "$status" -eq 0 ]
  local _entry
  for _entry in .claude/hooks/guard_command.py .claude/statusline/statusline.py .codex/hooks/hook_translation.py; do
    [ -x "$HOME_DIR/$_entry" ]
    [ "$(head -n 1 "$HOME_DIR/$_entry")" = "#!$FAKE_PYTHON -IB" ] || {
      echo "shebang not pinned: $_entry"
      return 1
    }
  done
  [ "$(head -n 1 "$HOME_DIR/.claude/hooks/lib/policy.py")" = '"""Shared policy."""' ]
}

@test "preserves settings Claude Code added while generated keys win" {
  mkdir -p "$HOME_DIR/.claude"
  printf '%s\n' '{"model":"stale","permissions":{"allow":["Bash(ls)"]}}' >|"$HOME_DIR/.claude/settings.json"

  run install_server

  [ "$status" -eq 0 ]
  [ "$(jq -r '.model' "$HOME_DIR/.claude/settings.json")" = "fable" ]
  [ "$(jq -r '.permissions.allow[0]' "$HOME_DIR/.claude/settings.json")" = "Bash(ls)" ]
}

@test "applies the host settings override after rendering" {
  mkdir -p "$HOME_DIR/.config/dotfiles"
  printf '%s\n' '{"sandbox":{"enabled":false}}' >|"$HOME_DIR/.config/dotfiles/claude_settings_override.json"

  run install_server

  [ "$status" -eq 0 ]
  [ "$(jq -r '.sandbox.enabled' "$HOME_DIR/.claude/settings.json")" = "false" ]
  [ "$(jq -r '.sandbox.network.allowedDomains[0]' "$HOME_DIR/.claude/settings.json")" = "api.day.app" ]
  [ "$(jq -r '.model' "$HOME_DIR/.claude/settings.json")" = "fable" ]
}

@test "fails when the harness verification fails" {
  run install_server FAKE_VERIFY_STATUS=3

  [ "$status" -ne 0 ]
  grep -Fq "verify --source" "$AGENT_HARNESS_ARGS_FILE"
}

# ============================================================
# Host-specific locations
# ============================================================

@test "loads host locations from the dotfiles config directory" {
  mkdir -p "$HOME_DIR/.config/dotfiles"
  printf '%s\n' \
    "BIN_DIR=\"$BATS_TEST_TMPDIR/tools\"" \
    "XDG_STATE_HOME=\"$BATS_TEST_TMPDIR/state\"" \
    >|"$HOME_DIR/.config/dotfiles/install_server.env"

  run install_server

  [ "$status" -eq 0 ]
  [ -x "$BATS_TEST_TMPDIR/tools/agent-harness" ]
  [ ! -e "$BIN_DIR" ]
  grep -Fq "XDG_STATE_HOME=\"$BATS_TEST_TMPDIR/state\"" "$HOME_DIR/.config/dotfiles/agent_env.sh"
}

@test "writes a shell snippet that puts the tools on PATH" {
  run install_server

  [ "$status" -eq 0 ]
  local _snippet="$HOME_DIR/.config/dotfiles/agent_env.sh"
  [[ "$output" == *"$_snippet"* ]]
  run env -i PATH=/usr/bin:/bin /bin/bash -c "source '$_snippet' && command -v rg"
  [ "$status" -eq 0 ]
  [ "$output" = "$BIN_DIR/rg" ]
}

@test "prints usage for --help" {
  run /bin/bash "$SCRIPT" --help

  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}
