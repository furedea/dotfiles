#!/usr/bin/env bats
# Executable specifications for the Nix-managed Hermes secretary profile.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PRIMARY_DOTFILES="$(dirname "$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir)")"
  HOME_CONFIG="homeConfigurations.kaito.config"
}

function build_secretary_package() {
  nix build --no-link --no-write-lock-file --print-out-paths --impure --expr \
    '{ flakeRef }:
    let
      flake = builtins.getFlake flakeRef;
      packages = flake.homeConfigurations.kaito.config.home.packages;
    in builtins.head (
      builtins.filter (package: (package.pname or package.name) == "secretary") packages
    )' \
    --argstr flakeRef "git+file://$REPO_ROOT"
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

@test "Home Manager leaves the existing Hermes profile environment untouched" {
  local _activation
  local _env_file="$BATS_TEST_TMPDIR/home/.hermes/profiles/secretary/.env"
  local _home="$BATS_TEST_TMPDIR/home"
  local _inode

  mkdir -p "$(dirname "$_env_file")"
  printf '%s\n' 'SLACK_BOT_TOKEN=local-credential' >"$_env_file"
  _inode="$(/usr/bin/stat -f '%i' "$_env_file")"

  run --separate-stderr get_hermes_activation
  [ "$status" -eq 0 ]
  _activation="$output"

  run env HOME="$_home" bash -c "$_activation"

  [ "$status" -eq 0 ]
  [ "$(/usr/bin/stat -f '%i' "$_env_file")" = "$_inode" ]
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
