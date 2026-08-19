#!/usr/bin/env bats
# Executable specifications for synchronizing owned GitHub repositories.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$GITHUB_DIR/sync_repos.sh"
  setup_sync_repo_stubs
}

@test "clones a missing owned repository into the canonical ghq path" {
  export GH_REPOSITORIES="furedea/alpha"

  run --separate-stderr bash "$SCRIPT"

  [ "$status" -eq 0 ]
  [[ "$(gh_calls)" == *"repo clone furedea/alpha $BATS_TEST_TMPDIR/ghq/github.com/furedea/alpha"* ]]
}

@test "fast-forwards the current branch of an existing repository" {
  export GH_REPOSITORIES="furedea/alpha"
  mkdir -p "$BATS_TEST_TMPDIR/ghq/github.com/furedea/alpha/.git"

  run --separate-stderr bash "$SCRIPT"

  [ "$status" -eq 0 ]
  [[ "$(git_calls)" == *"-C $BATS_TEST_TMPDIR/ghq/github.com/furedea/alpha pull --ff-only"* ]]
}

@test "refuses to overwrite a non-Git path matching a repository" {
  export GH_REPOSITORIES="furedea/alpha"
  local _target="$BATS_TEST_TMPDIR/ghq/github.com/furedea/alpha"
  mkdir -p "$_target"
  printf 'keep\n' >"$_target/sentinel"

  run --separate-stderr bash "$SCRIPT"

  [ "$status" -eq 1 ]
  [ "$(cat "$_target/sentinel")" = "keep" ]
  [ -z "$(git_calls)" ]
  [[ "$(gh_calls)" != *"repo clone furedea/alpha"* ]]
}

@test "continues synchronizing after a repository fails" {
  export GH_REPOSITORIES=$'furedea/alpha\nfuredea/beta'
  export GIT_PULL_FAILURE="/alpha"
  mkdir -p "$BATS_TEST_TMPDIR/ghq/github.com/furedea/alpha/.git"

  run --separate-stderr bash "$SCRIPT"

  [ "$status" -eq 1 ]
  [[ "$(gh_calls)" == *"repo clone furedea/beta $BATS_TEST_TMPDIR/ghq/github.com/furedea/beta"* ]]
}

@test "dry run leaves repositories unchanged" {
  export GH_REPOSITORIES=$'furedea/alpha\nfuredea/beta'
  mkdir -p "$BATS_TEST_TMPDIR/ghq/github.com/furedea/alpha/.git"

  run --separate-stderr bash "$SCRIPT" --dry-run

  [ "$status" -eq 0 ]
  [ -z "$(git_calls)" ]
  [[ "$(gh_calls)" != *"repo clone"* ]]
  [ ! -e "$BATS_TEST_TMPDIR/ghq/github.com/furedea/beta" ]
}

@test "dry run reports planned repository operations" {
  export GH_REPOSITORIES=$'furedea/alpha\nfuredea/beta'
  mkdir -p "$BATS_TEST_TMPDIR/ghq/github.com/furedea/alpha/.git"

  run --separate-stderr bash "$SCRIPT" --dry-run

  [ "$status" -eq 0 ]
  [[ "$output" == *"[pull] $BATS_TEST_TMPDIR/ghq/github.com/furedea/alpha"* ]]
  [[ "$output" == *"[clone] furedea/beta -> $BATS_TEST_TMPDIR/ghq/github.com/furedea/beta"* ]]
}

@test "reports synchronization totals" {
  export GH_REPOSITORIES=$'furedea/alpha\nfuredea/beta\nfuredea/gamma'
  mkdir -p "$BATS_TEST_TMPDIR/ghq/github.com/furedea/alpha/.git"
  mkdir -p "$BATS_TEST_TMPDIR/ghq/github.com/furedea/gamma"

  run --separate-stderr bash "$SCRIPT"

  [ "$status" -eq 1 ]
  [[ "$output" == *"[summary] cloned=1 pulled=1 failed=1"* ]]
}
