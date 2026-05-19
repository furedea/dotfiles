#!/usr/bin/env bats
# Tests for github/create_repo.sh

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$GITHUB_DIR/create_repo.sh"
  setup_create_repo_stubs
}

@test "shows usage when no argument is given" {
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "rejects --clone because the script controls the local destination" {
  run bash "$SCRIPT" agent-harness --private --clone
  [ "$status" -eq 1 ]
  [[ "$output" == *"do not pass --clone"* ]]
}

@test "creates a template repository and prints only the clone destination to stdout" {
  run --separate-stderr bash "$SCRIPT" agent-harness --private --template furedea/template-rust
  [ "$status" -eq 0 ]
  [ "$output" = "$BATS_TEST_TMPDIR/ghq/github.com/furedea/agent-harness" ]
  [[ "$stderr" == *"creating GitHub repo"* ]]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"api user --jq .login"* ]]
  [[ "$calls" == *"repo create agent-harness --private --template furedea/template-rust"* ]]
  [[ "$calls" == *"api repos/furedea/agent-harness --jq .default_branch // empty"* ]]
  [[ "$calls" == *"api repos/furedea/agent-harness/git/ref/heads/main --jq .ref // empty"* ]]
  [[ "$calls" == *"repo clone furedea/agent-harness $BATS_TEST_TMPDIR/ghq/github.com/furedea/agent-harness"* ]]
}

@test "keeps waiting when GitHub returns an empty repository response for the branch ref" {
  GH_REF_EMPTY_ONCE=1 run bash "$SCRIPT" agent-harness --private --template furedea/template-rust
  [ "$status" -eq 0 ]

  local calls ref_calls
  calls="$(gh_calls)"
  ref_calls=$(grep -c "git/ref/heads/main" "$GH_LOG")
  [ "$ref_calls" -eq 2 ]
  [[ "$calls" == *"repo clone furedea/agent-harness $BATS_TEST_TMPDIR/ghq/github.com/furedea/agent-harness"* ]]
}

@test "rewrites Rust template package name after clone" {
  run bash "$SCRIPT" agent-harness --private --template furedea/template-rust
  [ "$status" -eq 0 ]

  local cargo_toml="$BATS_TEST_TMPDIR/ghq/github.com/furedea/agent-harness/Cargo.toml"
  [[ -f "$cargo_toml" ]]
  grep -q '^name = "agent-harness"$' "$cargo_toml"
}

@test "fails before remote creation when local destination already exists" {
  mkdir -p "$BATS_TEST_TMPDIR/ghq/github.com/furedea/agent-harness"

  run bash "$SCRIPT" agent-harness --private --template furedea/template-rust
  [ "$status" -eq 1 ]
  [[ "$output" == *"local destination already exists"* ]]
  ! grep -q "repo create" "$GH_LOG"
}
