#!/usr/bin/env bats
# Validate the generated Codex permissions config that auto-locks hook files.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  PYTHON="$(nix build --no-link --print-out-paths "$REPO_ROOT#python3")/bin/python"
}

fragment_toml() {
  nix eval --raw "$REPO_ROOT#lib.codexConfigFragmentToml"
}

filesystem_entries() {
  nix eval --json "$REPO_ROOT#lib.codexFilesystemPermissions"
}

@test "generated codex fragment is valid TOML" {
  toml="$(fragment_toml)"
  printf '%s' "$toml" | "$PYTHON" -c 'import sys, tomllib; tomllib.loads(sys.stdin.read())'
}

@test "generated codex fragment exposes guarded filesystem section with glob depth" {
  toml="$(fragment_toml)"
  printf '%s' "$toml" | "$PYTHON" -c '
import sys, tomllib
data = tomllib.loads(sys.stdin.read())
filesystem = data["permissions"]["guarded"]["filesystem"]
assert filesystem["glob_scan_max_depth"] >= 3, filesystem
'
}

@test "codex/config.toml declares default_permissions at top level" {
  # `default_permissions` MUST stay above any `[<table>]` header — TOML folds
  # bare scalars into the most recent table, so placing it inside the
  # appended `[permissions.guarded.filesystem]` fragment would silently
  # promote it to `permissions.guarded.filesystem.default_permissions`.
  CONFIG="$REPO_ROOT/codex/config.toml" "$PYTHON" -c '
import os, tomllib, pathlib
data = tomllib.loads(pathlib.Path(os.environ["CONFIG"]).read_text())
assert data["default_permissions"] == "guarded", data
'
}

@test "merged Codex config keeps default_permissions and locks hook files" {
  source_file="$BATS_TEST_TMPDIR/source.toml"
  target_file="$BATS_TEST_TMPDIR/target.toml"

  cat "$REPO_ROOT/codex/config.toml" >"$source_file"
  printf '\n' >>"$source_file"
  fragment_toml >>"$source_file"
  : >"$target_file"

  "$PYTHON" "$REPO_ROOT/codex/sync_config.py" "$source_file" "$target_file"

  TARGET="$target_file" "$PYTHON" -c '
import os, tomllib, pathlib
data = tomllib.loads(pathlib.Path(os.environ["TARGET"]).read_text())
assert data["default_permissions"] == "guarded", data
filesystem = data["permissions"]["guarded"]["filesystem"]
assert filesystem["glob_scan_max_depth"] == 5
assert all(v == "read" for k, v in filesystem.items() if k != "glob_scan_max_depth")
assert "$HOME/.claude/hooks/command_allowlist.sh" in filesystem
assert "$HOME/.codex/hooks/adapt_shell_command.sh" in filesystem
'
}

@test "generated codex fragment locks every file under agents/hooks/ and codex/hooks/" {
  dotfiles_name="$(basename "$REPO_ROOT")"

  expected="$(
    {
      cd "$REPO_ROOT/agents/hooks" && find . -type f -print |
        sed 's|^\./|$HOME/.claude/hooks/|'
      cd "$REPO_ROOT/codex/hooks" && find . -type f -print |
        sed 's|^\./|$HOME/.codex/hooks/|'
      cd "$REPO_ROOT/agents/hooks" && find . -type f -print |
        sed "s|^\./|**/${dotfiles_name}/agents/hooks/|"
      cd "$REPO_ROOT/codex/hooks" && find . -type f -print |
        sed "s|^\./|**/${dotfiles_name}/codex/hooks/|"
      printf '%s\n' \
        '$HOME/.claude/CLAUDE.md' \
        '$HOME/.claude/settings.json' \
        '$HOME/.codex/AGENTS.md' \
        '$HOME/.codex/hooks.json' \
        '$HOME/.codex/rules/default.rules' \
        "**/${dotfiles_name}/agents/AGENTS.md" \
        "**/${dotfiles_name}/codex/hooks.json"
    } | sort -u
  )"

  actual="$(filesystem_entries | jq -r 'to_entries[] | select(.key != "glob_scan_max_depth") | .key' | sort)"

  [ "$actual" = "$expected" ]
}

@test "generated codex fragment marks every locked path as read-only" {
  filesystem_entries | jq -e '
    to_entries
    | map(select(.key != "glob_scan_max_depth"))
    | all(.value == "read")
  ' >/dev/null
}

@test "generated codex fragment excludes agents/skills/ from auto-lock" {
  ! filesystem_entries | jq -e 'keys[] | select(test("/skills/"))' >/dev/null
}

@test "home-manager wires codex permissions through sync_config.py source" {
  HOME_NIX="$REPO_ROOT/nix/home/default.nix"

  grep -q 'codexSettings = import ../agents/codex_settings.nix' "$HOME_NIX"
  grep -q 'codexSettings.configFragmentToml' "$HOME_NIX"
}
