#!/usr/bin/env bats
# Executable specifications for updating the pinned moshi-hook release.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/scripts/moshi/update_moshi_hook.sh"
  PACKAGE="$BATS_TEST_TMPDIR/moshi_hook.nix"
  CDN="$BATS_TEST_TMPDIR/cdn"
  NEW_HEX="a883c33f06a7a7a0de6e2bdeaca3c252ce0ad999c79c199586f748212f54ebfd"
  NEW_SRI="sha256-qIPDPwanp6DebiverKPCUs4K2ZnHnBmVhvdIIS9U6/0="
  OLD_SRI="sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
  sed \
    -e 's/^  version = ".*";$/  version = "0.3.21";/' \
    -e "s|^    hash = \".*\";$|    hash = \"$OLD_SRI\";|" \
    "$REPO_ROOT/nix/packages/moshi_hook.nix" >"$PACKAGE"
  cp "$PACKAGE" "$BATS_TEST_TMPDIR/original.nix"
}

@test "newer release rewrites only the version and hash" {
  publish_release v0.4.31 "$NEW_HEX  moshi-hook_Darwin_arm64.tar.gz"

  run --separate-stderr update_package

  [ "$status" -eq 0 ]
  [ "$output" = "0.4.31" ]
  run diff "$BATS_TEST_TMPDIR/original.nix" "$PACKAGE"
  [ "${lines[1]}" = '<   version = "0.3.21";' ]
  [ "${lines[3]}" = '>   version = "0.4.31";' ]
  [ "${lines[5]}" = "<     hash = \"$OLD_SRI\";" ]
  [ "${lines[7]}" = ">     hash = \"$NEW_SRI\";" ]
  [ "${#lines[@]}" -eq 8 ]
}

@test "same release reports no update and leaves the file unchanged" {
  publish_release v0.3.21 "$NEW_HEX  moshi-hook_Darwin_arm64.tar.gz"

  run --separate-stderr update_package

  [ "$status" -eq 3 ]
  [ -z "$output" ]
  cmp "$BATS_TEST_TMPDIR/original.nix" "$PACKAGE"
}

@test "release without the Darwin arm64 checksum fails without rewriting" {
  publish_release v0.4.31 "$NEW_HEX  moshi-hook_Linux_x86_64.tar.gz"

  run --separate-stderr update_package

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"moshi-hook_Darwin_arm64.tar.gz"* ]]
  cmp "$BATS_TEST_TMPDIR/original.nix" "$PACKAGE"
}

@test "malformed latest version fails without rewriting" {
  publish_release 0.4.31 "$NEW_HEX  moshi-hook_Darwin_arm64.tar.gz"

  run --separate-stderr update_package

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"0.4.31"* ]]
  cmp "$BATS_TEST_TMPDIR/original.nix" "$PACKAGE"
}

function publish_release() {
  local _tag="$1"
  local _checksums="$2"
  mkdir -p "$CDN/latest" "$CDN/$_tag"
  printf '%s' "$_tag" >"$CDN/latest/version.txt"
  printf '%s\n' "$_checksums" >"$CDN/$_tag/checksums.txt"
}

function update_package() {
  MOSHI_CDN_URL="file://$CDN" /bin/bash "$SCRIPT" "$PACKAGE"
}
