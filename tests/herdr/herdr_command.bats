#!/usr/bin/env bats
# Executable specifications for Nix-managed Herdr command helpers.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PRIMARY_DOTFILES="$(dirname "$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir)")"
  HOME_CONFIG="homeConfigurations.kaito.config"
}

@test "Herdr launcher pins Python while keeping the implementation editable" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#$HOME_CONFIG.home.file.\".local/libexec/herdr_merge_pull_request.sh\".source"

  [ "$status" -eq 0 ]
  local _launcher="$output"
  grep -Eq 'exec /nix/store/[^ ]+/bin/python3[^ ]* -I -B ' "$_launcher"
  grep -Fq "$PRIMARY_DOTFILES/herdr/merge_pull_request.py" "$_launcher"
  mkdir -p "$BATS_TEST_TMPDIR/empty-path"
  run env PATH="$BATS_TEST_TMPDIR/empty-path" "$_launcher"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "Home Manager builds with the out-of-store Herdr pull-request merge helper" {
  run --separate-stderr nix build --no-link --print-out-paths \
    "$REPO_ROOT#homeConfigurations.kaito.activationPackage"

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]
}
