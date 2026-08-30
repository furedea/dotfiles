#!/usr/bin/env bats
# Executable specifications for the Nix-managed Hermes secretary profile.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PRIMARY_DOTFILES="$(dirname "$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir)")"
  HOME_CONFIG="homeConfigurations.kaito.config"
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

@test "Home Manager keeps Hermes cron state local" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$HOME_CONFIG.home.file" \
    --apply \
    'files: builtins.hasAttr ".hermes/profiles/secretary/cron" files'

  [ "$status" -eq 0 ]
  [ "$output" = 'false' ]
}

@test "Home Manager initializes the secretary with the Hermes profile CLI" {
  local _activation
  local _home="$BATS_TEST_TMPDIR/home"

  run --separate-stderr nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#$HOME_CONFIG.home.activation.initializeHermesSecretary.data"

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

@test "Home Manager installs apple-mail-cli" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$HOME_CONFIG.home.packages" \
    --apply \
    'packages:
      builtins.any
        (package: (package.pname or package.name) == "apple-mail-cli")
        packages'

  [ "$status" -eq 0 ]
  [ "$output" = 'true' ]
}

@test "Home Manager does not install Himalaya" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$HOME_CONFIG.home.packages" \
    --apply \
    'packages:
      builtins.any
        (package: (package.pname or package.name) == "himalaya")
        packages'

  [ "$status" -eq 0 ]
  [ "$output" = 'false' ]
}

@test "Home Manager installs a dedicated secretary CLI" {
  local _secretary_path

  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$HOME_CONFIG.home.packages" \
    --apply \
    'packages:
      builtins.filter
        (name: name == "secretary")
        (map (package: package.pname or package.name) packages)'

  [ "$status" -eq 0 ]
  [ "$output" = '["secretary"]' ]

  run --separate-stderr nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#$HOME_CONFIG.home.packages" \
    --apply \
    'packages:
      (builtins.head
        (builtins.filter
          (package: (package.pname or package.name) == "secretary")
          packages)).outPath'
  [ "$status" -eq 0 ]
  _secretary_path="$output"
  grep -Fq 'exec hermes -p secretary "$@"' "$_secretary_path/bin/secretary"
}

@test "The Hermes secretary exposes focused skills" {
  local _skill

  for _skill in \
    apple-mail \
    calendar-briefing \
    mail-triage \
    morning-briefing; do
    [ -f "$REPO_ROOT/hermes/secretary/skills/secretary/$_skill/SKILL.md" ]
    grep -Fq "name: $_skill" \
      "$REPO_ROOT/hermes/secretary/skills/secretary/$_skill/SKILL.md"
    grep -Fq '## When to Use' \
      "$REPO_ROOT/hermes/secretary/skills/secretary/$_skill/SKILL.md"
  done
}

@test "The morning routine is a read-only Hermes blueprint" {
  local _skill="$REPO_ROOT/hermes/secretary/skills/secretary/morning-briefing/SKILL.md"

  grep -Fq 'blueprint:' "$_skill"
  grep -Fq 'schedule: "0 8 * * *"' "$_skill"
  grep -Fq 'prompt: Prepare today' "$_skill"
  grep -Fq 'Keep the run read-only.' "$_skill"
  grep -Fq 'enabled_toolsets: [terminal, skills]' "$_skill"
}
