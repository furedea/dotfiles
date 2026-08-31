#!/usr/bin/env bats
# Executable specifications for the Nix-managed Hermes secretary profile.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PRIMARY_DOTFILES="$(dirname "$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir)")"
  HOME_CONFIG="homeConfigurations.kaito.config"
}

function build_home_package_output() {
  local _package_name="${1:?package name is required}"
  local _output="${2:?output is required}"

  nix build --no-link --print-out-paths --impure --expr \
    '{ output, packageName }:
    let
      flake = builtins.getFlake "git+file://'"$REPO_ROOT"'";
      packages = flake.homeConfigurations.kaito.config.home.packages;
      package = builtins.head (
        builtins.filter
          (candidate: (candidate.pname or candidate.name) == packageName)
          packages
      );
    in if output == "package" then package else builtins.getAttr output package' \
    --argstr output "$_output" \
    --argstr packageName "$_package_name"
}

function build_hermes_package() {
  build_home_package_output hermes-agent package
}

function build_hermes_venv() {
  build_home_package_output hermes-agent hermesVenv
}

function build_secretary_package() {
  build_home_package_output secretary package
}

function get_hermes_activation() {
  nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#$HOME_CONFIG.home.activation.initializeHermesSecretary.data"
}

@test "Home Manager links Hermes secretary files from the editable dotfiles tree" {
  local _managed_path
  local _source_path

  while IFS='|' read -r _managed_path _source_path; do
    run --separate-stderr nix build --no-link --print-out-paths \
      "$REPO_ROOT#$HOME_CONFIG.home.file.\"$_managed_path\".source"

    [ "$status" -eq 0 ]
    run readlink "$output"
    [ "$status" -eq 0 ]
    [ "$output" = "$PRIMARY_DOTFILES/$_source_path" ]
  done <<'EOF'
.hermes/profiles/secretary/SOUL.md|hermes/secretary/SOUL.md
.hermes/profiles/secretary/skills/secretary|hermes/secretary/skills/secretary
EOF
}

@test "Home Manager keeps mutable Hermes profile state local" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$HOME_CONFIG.home.file" \
    --apply \
    'files:
      builtins.all
        (path: !(builtins.hasAttr path files))
        [
          ".hermes/profiles/secretary/cron"
          ".hermes/profiles/secretary/state"
          ".hermes/profiles/secretary/.env"
          ".hermes/profiles/secretary/config.yaml"
        ]'

  [ "$status" -eq 0 ]
  [ "$output" = 'true' ]
}

@test "Home Manager leaves the existing Hermes profile environment untouched" {
  local _activation
  local _env_file="$BATS_TEST_TMPDIR/home/.hermes/profiles/secretary/.env"
  local _home="$BATS_TEST_TMPDIR/home"
  local _inode

  mkdir -p "$(dirname "$_env_file")"
  printf '%s\n' 'SLACK_BOT_TOKEN=local-credential' >"$_env_file"
  _inode="$(stat -f '%i' "$_env_file")"

  run --separate-stderr get_hermes_activation
  [ "$status" -eq 0 ]
  _activation="$output"

  run env HOME="$_home" bash -c "$_activation"

  [ "$status" -eq 0 ]
  [ "$(stat -f '%i' "$_env_file")" = "$_inode" ]
  [ "$(<"$_env_file")" = 'SLACK_BOT_TOKEN=local-credential' ]
}

@test "Home Manager initializes the secretary with the Hermes profile CLI" {
  local _activation
  local _home="$BATS_TEST_TMPDIR/home"

  run --separate-stderr get_hermes_activation

  [ "$status" -eq 0 ]
  [[ "$output" == *'profile create secretary --no-skills --no-alias'* ]]
  _activation="$output"

  mkdir -p "$_home"
  run env HOME="$_home" bash -c "$_activation"

  [ "$status" -eq 0 ]
  [ -f "$_home/.hermes/profiles/secretary/.env" ]
  [ -f "$_home/.hermes/profiles/secretary/.no-bundled-skills" ]
  [ ! -e "$_home/.hermes/profiles/secretary/SOUL.md" ]
  [ ! -e "$_home/.local/bin/secretary" ]
}

@test "Home Manager installs a dedicated secretary CLI" {
  local _secretary_path

  run --separate-stderr build_secretary_package
  [ "$status" -eq 0 ]
  _secretary_path="$output"

  grep -Fq 'exec hermes -p secretary "$@"' "$_secretary_path/bin/secretary"
}

@test "The Hermes secretary can load the Slack gateway dependencies" {
  local _hermes_venv

  run --separate-stderr build_hermes_venv

  [ "$status" -eq 0 ]
  _hermes_venv="$output"

  run "$_hermes_venv/bin/python3" -c \
    'from plugins.platforms.slack.adapter import SLACK_AVAILABLE; raise SystemExit(not SLACK_AVAILABLE)'

  [ "$status" -eq 0 ]
}

@test "The launchd gateway does not persist credential environment variables" {
  local _hermes_venv
  local _home="$BATS_TEST_TMPDIR/home"

  run --separate-stderr build_hermes_venv
  [ "$status" -eq 0 ]
  _hermes_venv="$output"

  mkdir -p "$_home"
  run env \
    HOME="$_home" \
    HERMES_BUNDLED_PLUGINS="/nix/store/bundled-plugins" \
    "$_hermes_venv/bin/python3" \
    -c '
import os
import plistlib

from hermes_cli.gateway import generate_launchd_plist

credential_names = {"OPENAI_API_KEY", "SLACK_BOT_TOKEN"}
for name in credential_names:
    os.environ[name] = "credential-sentinel"
environment = plistlib.loads(generate_launchd_plist().encode())["EnvironmentVariables"]
print("\n".join(sorted(credential_names & environment.keys())))
'

  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "The launchd gateway discovers the bundled Slack plugin" {
  local _hermes_package
  local _hermes_venv
  local _home="$BATS_TEST_TMPDIR/home"

  run --separate-stderr build_hermes_package
  [ "$status" -eq 0 ]
  _hermes_package="$output"

  run --separate-stderr build_hermes_venv
  [ "$status" -eq 0 ]
  _hermes_venv="$output"

  mkdir -p "$_home"
  run env \
    HOME="$_home" \
    HERMES_BUNDLED_PLUGINS="$_hermes_package/share/hermes-agent/plugins" \
    "$_hermes_venv/bin/python3" \
    -c '
import os
import plistlib
import subprocess
import sys

from hermes_cli.gateway import generate_launchd_plist

service = plistlib.loads(generate_launchd_plist().encode())
service_environment = os.environ.copy()
service_environment.pop("HERMES_BUNDLED_PLUGINS", None)
service_environment.update(service["EnvironmentVariables"])
result = subprocess.run(
    [sys.executable, "-m", "hermes_cli.main", "plugins", "list", "--plain"],
    capture_output=True,
    check=False,
    env=service_environment,
    text=True,
)
print(result.stdout, end="")
raise SystemExit(result.returncode)
'

  [ "$status" -eq 0 ]
  [[ "$output" == *"slack-platform"* ]]
}

@test "The Hermes secretary exposes focused skills" {
  local _skill

  for _skill in \
    apple-mail \
    calendar-briefing \
    google-calendar \
    mail-triage \
    morning-briefing \
    research-digest \
    tech-digest; do
    [ -f "$REPO_ROOT/hermes/secretary/skills/secretary/$_skill/SKILL.md" ]
    grep -Fq "name: $_skill" \
      "$REPO_ROOT/hermes/secretary/skills/secretary/$_skill/SKILL.md"
    grep -Fq '## When to Use' \
      "$REPO_ROOT/hermes/secretary/skills/secretary/$_skill/SKILL.md"
  done
}

@test "The morning routine limits writes to local digest state" {
  local _skill="$REPO_ROOT/hermes/secretary/skills/secretary/morning-briefing/SKILL.md"

  grep -Fq 'blueprint:' "$_skill"
  grep -Fq 'schedule: "0 8 * * *"' "$_skill"
  grep -Fq 'prompt: Prepare today' "$_skill"
  grep -Fq \
    'Keep providers read-only; only local digest state may change.' \
    "$_skill"
  grep -Fq 'enabled_toolsets: [terminal, skills]' "$_skill"
}
