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
.hermes/profiles/secretary/cron|hermes/secretary/cron
EOF
}

@test "Home Manager installs the Hermes secretary data clients" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#$HOME_CONFIG.home.packages" \
    --apply \
    'packages:
      builtins.filter
        (name: builtins.elem name [ "himalaya" "khal" "vdirsyncer" ])
        (map (package: package.pname or package.name) packages)'

  [ "$status" -eq 0 ]
  [ "$output" = '["himalaya","khal","vdirsyncer"]' ]
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

@test "Homebrew installs the official X API client" {
  run --separate-stderr nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#darwinConfigurations.mba.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" == *'cask "xdevplatform/tap/xurl"'* ]]
}

@test "Homebrew trusts only xurl from the X developer platform tap" {
  run --separate-stderr nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#darwinConfigurations.mba.config.homebrew.brewfile"

  [ "$status" -eq 0 ]
  [[ "$output" == *'tap "xdevplatform/tap", trusted: { cask: "xurl" }'* ]]
  [[ "$output" != *'tap "xdevplatform/tap", trusted: true'* ]]
}

@test "The Hermes secretary exposes four focused skills" {
  local _skill

  for _skill in calendar-briefing mail-triage morning-briefing x-morning-digest; do
    [ -f "$REPO_ROOT/hermes/secretary/skills/secretary/$_skill/SKILL.md" ]
    grep -Fq "name: $_skill" \
      "$REPO_ROOT/hermes/secretary/skills/secretary/$_skill/SKILL.md"
  done
}

@test "Mail triage uses account-scoped Himalaya 1.x commands" {
  local _skill="$REPO_ROOT/hermes/secretary/skills/secretary/mail-triage/SKILL.md"

  grep -Fq \
    'himalaya envelope list --account ACCOUNT --output json --page-size LIMIT' \
    "$_skill"
  ! grep -Fq 'himalaya --account' "$_skill"
}

@test "Cron tracks only the routine definition" {
  run jq -e '.jobs == []' "$REPO_ROOT/hermes/secretary/cron/jobs.json"
  [ "$status" -eq 0 ]

  run git -C "$REPO_ROOT" check-ignore --no-index \
    hermes/secretary/cron/output/example/run.json
  [ "$status" -eq 0 ]

  run git -C "$REPO_ROOT" check-ignore --no-index \
    hermes/secretary/cron/jobs.json
  [ "$status" -eq 1 ]
}
