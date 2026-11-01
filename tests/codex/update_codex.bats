#!/usr/bin/env bats
# Executable specifications for updating the pinned official Codex release.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/scripts/codex/update_codex.sh"
  PACKAGE="$BATS_TEST_TMPDIR/codex.nix"
  RELEASES="$BATS_TEST_TMPDIR/releases.json"
  ASSET="codex-package-aarch64-apple-darwin.tar.gz"
  NEW_HEX="a883c33f06a7a7a0de6e2bdeaca3c252ce0ad999c79c199586f748212f54ebfd"
  NEW_SRI="sha256-qIPDPwanp6DebiverKPCUs4K2ZnHnBmVhvdIIS9U6/0="
  OLD_SRI="sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
  sed \
    -e 's/^  version = ".*";$/  version = "0.160.0";/' \
    -e "s|^    hash = \".*\";$|    hash = \"$OLD_SRI\";|" \
    "$REPO_ROOT/nix/packages/codex.nix" >"$PACKAGE"
  cp "$PACKAGE" "$BATS_TEST_TMPDIR/original.nix"
}

@test "newer stable release rewrites only the version and hash" {
  publish_releases \
    "$(release rust-v0.161.0 false false "$ASSET" "sha256:$NEW_HEX")" \
    "$(release rust-v0.160.0 false false "$ASSET" "sha256:$(printf '0%.0s' {1..64})")"

  run --separate-stderr update_package

  [ "$status" -eq 0 ]
  [ "$output" = "0.161.0" ]
  run diff "$BATS_TEST_TMPDIR/original.nix" "$PACKAGE"
  [ "${lines[1]}" = '<   version = "0.160.0";' ]
  [ "${lines[3]}" = '>   version = "0.161.0";' ]
  [ "${lines[5]}" = "<     hash = \"$OLD_SRI\";" ]
  [ "${lines[7]}" = ">     hash = \"$NEW_SRI\";" ]
  [ "${#lines[@]}" -eq 8 ]
}

@test "prereleases and drafts are ignored" {
  publish_releases \
    "$(release rust-v0.163.0-alpha.2 true false "$ASSET" "sha256:$NEW_HEX")" \
    "$(release rust-v0.162.0 false true "$ASSET" "sha256:$NEW_HEX")" \
    "$(release rust-v0.161.0 false false "$ASSET" "sha256:$NEW_HEX")"

  run --separate-stderr update_package

  [ "$status" -eq 0 ]
  [ "$output" = "0.161.0" ]
}

@test "current release reports no update and leaves the file unchanged" {
  publish_releases \
    "$(release rust-v0.163.0-alpha.2 true false "$ASSET" "sha256:$NEW_HEX")" \
    "$(release rust-v0.160.0 false false "$ASSET" "sha256:$NEW_HEX")"

  run --separate-stderr update_package

  [ "$status" -eq 3 ]
  [ -z "$output" ]
  cmp "$BATS_TEST_TMPDIR/original.nix" "$PACKAGE"
}

@test "release without the package digest fails without rewriting" {
  publish_releases \
    "$(release rust-v0.161.0 false false codex-aarch64-apple-darwin.tar.gz "sha256:$NEW_HEX")"

  run --separate-stderr update_package

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"$ASSET"* ]]
  cmp "$BATS_TEST_TMPDIR/original.nix" "$PACKAGE"
}

@test "releases without a stable tag fail without rewriting" {
  publish_releases \
    "$(release rust-v0.161.0-alpha.1 true false "$ASSET" "sha256:$NEW_HEX")" \
    "$(release v0.161.0 false false "$ASSET" "sha256:$NEW_HEX")"

  run --separate-stderr update_package

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"no stable"* ]]
  cmp "$BATS_TEST_TMPDIR/original.nix" "$PACKAGE"
}

function release() {
  jq --null-input --compact-output \
    --arg tag "$1" --argjson prerelease "$2" --argjson draft "$3" \
    --arg asset "$4" --arg digest "$5" \
    '{tag_name: $tag, prerelease: $prerelease, draft: $draft,
      assets: [{name: $asset, digest: $digest}]}'
}

function publish_releases() {
  printf '%s\n' "$@" | jq --slurp '.' >"$RELEASES"
}

function update_package() {
  CODEX_RELEASES_URL="file://$RELEASES" /bin/bash "$SCRIPT" "$PACKAGE"
}
