#!/usr/bin/env bats
# Executable specifications for Zsh repository search behavior.

bats_require_minimum_version 1.5.0

setup_file() {
  load test-helper/repository_search
  setup_repository_search_fixture
}

setup() {
  load test-helper/setup
  load test-helper/repository_search
  setup_zsh_test_environment
  setup_repository_search_stubs
}

@test "repository search includes a registered worktree outside the ghq root" {
  run_repository_search false

  [ "$status" -eq 0 ]
  [ "$output" = "builtin cd $TEST_WORKTREE" ]
  [[ "$stderr" != *"root not found"* ]]
}

@test "repository search avoids roots errors for ghq-listed worktrees" {
  run_repository_search true

  [ "$status" -eq 0 ]
  [ "$output" = "builtin cd $TEST_WORKTREE" ]
  [[ "$stderr" != *"root not found"* ]]
}
