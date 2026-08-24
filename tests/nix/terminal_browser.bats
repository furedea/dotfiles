#!/usr/bin/env bats
# Executable specifications for the terminal-browser package.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

function terminal_browser_attribute() {
  local _attribute="$1"

  nix eval --no-write-lock-file --raw \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.packages" \
    --apply \
    "packages:
      (builtins.head
        (builtins.filter
          (package: (package.pname or \"\") == \"terminal-browser\")
          packages)).$_attribute"
}

@test "Home Manager installs terminal-browser version 0.6.0" {
  run --separate-stderr nix eval --no-write-lock-file --json \
    "$REPO_ROOT#homeConfigurations.kaito.config.home.packages" \
    --apply \
    'packages:
      map
        (package: package.version)
        (builtins.filter (package: (package.pname or "") == "terminal-browser") packages)'

  [ "$status" -eq 0 ]
  [ "$output" = '["0.6.0"]' ]
}

@test "terminal-browser runs through a Home Manager profile symlink" {
  local _package_drv
  local _package_path
  local _profile_bin="$BATS_TEST_TMPDIR/profile/bin"

  run --separate-stderr terminal_browser_attribute drvPath
  [ "$status" -eq 0 ]
  _package_drv="$output"

  run --separate-stderr terminal_browser_attribute outPath
  [ "$status" -eq 0 ]
  _package_path="$output"

  run nix build --no-link "$_package_drv^*"
  [ "$status" -eq 0 ]

  mkdir -p "$_profile_bin"
  ln -s "$_package_path/bin/terminal-browser" "$_profile_bin/terminal-browser"

  run "$_profile_bin/terminal-browser" --version

  [ "$status" -eq 0 ]
  [ "$output" = "terminal-browser v0.6.0" ]
}
