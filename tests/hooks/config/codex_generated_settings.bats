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

@test "codex/config.toml does not select guarded permissions by default" {
  CONFIG="$REPO_ROOT/codex/config.toml" "$PYTHON" -c '
import os, tomllib, pathlib
data = tomllib.loads(pathlib.Path(os.environ["CONFIG"]).read_text())
assert "default_permissions" not in data, data
'
}

@test "merged Codex config removes stale default_permissions and keeps guarded profile available" {
  source_file="$BATS_TEST_TMPDIR/source.toml"
  target_file="$BATS_TEST_TMPDIR/target.toml"

  cat "$REPO_ROOT/codex/config.toml" >"$source_file"
  printf '\n' >>"$source_file"
  fragment_toml >>"$source_file"
  printf 'default_permissions = "guarded"\n' >"$target_file"

  "$PYTHON" "$REPO_ROOT/codex/sync_config.py" "$source_file" "$target_file"

  TARGET="$target_file" "$PYTHON" -c '
import os, tomllib, pathlib
data = tomllib.loads(pathlib.Path(os.environ["TARGET"]).read_text())
assert "default_permissions" not in data, data
filesystem = data["permissions"]["guarded"]["filesystem"]
assert filesystem["glob_scan_max_depth"] == 5
assert all(v == "read" for k, v in filesystem.items() if k != "glob_scan_max_depth")
assert "~/.claude/hooks/guard_allowed_commands.sh" in filesystem
assert "~/.codex/hooks/adapt_shell_command.sh" in filesystem
'
}

@test "generated codex fragment locks every file under agents/hooks/ and codex/hooks/" {
  tilde_dotfiles_home_path="$(nix eval --raw "$REPO_ROOT#lib.dotfilesHomePath")"

  # Use git ls-files (not find) so the expected set matches what Nix's
  # flake-aware source path sees — gitignored runtime artifacts (e.g. audit
  # logs under agents/hooks/docs/logs/) must not enter the lock list.
  expected="$(
    {
      cd "$REPO_ROOT" && git ls-files agents/hooks |
        sed 's|^agents/hooks/|~/.claude/hooks/|'
      cd "$REPO_ROOT" && git ls-files codex/hooks |
        sed 's|^codex/hooks/|~/.codex/hooks/|'
      cd "$REPO_ROOT" && git ls-files agents/hooks |
        sed "s|^agents/hooks/|${tilde_dotfiles_home_path}/agents/hooks/|"
      cd "$REPO_ROOT" && git ls-files codex/hooks |
        sed "s|^codex/hooks/|${tilde_dotfiles_home_path}/codex/hooks/|"
      printf '%s\n' \
        '~/.claude/CLAUDE.md' \
        '~/.claude/rules/forbidden_commands.json' \
        '~/.claude/settings.json' \
        '~/.codex/AGENTS.md' \
        '~/.codex/hooks.json' \
        '~/.codex/rules/default.rules' \
        "${tilde_dotfiles_home_path}/agents/AGENTS.md"
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
