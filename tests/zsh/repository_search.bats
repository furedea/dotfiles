#!/usr/bin/env bats
# Executable specifications for Zsh repository search behavior.

bats_require_minimum_version 1.5.0

setup_file() {
  load test-helper/repository_search.bash
  setup_repository_search_fixture
}

setup() {
  load test-helper/repository_search.bash
  setup_zsh_test_environment
  setup_repository_search_stubs
}

@test "repository search limits worktrees to ghq candidates" {
  run_repository_search

  [ "$status" -eq 0 ]
  [ "$output" = "builtin cd $TEST_WORKTREE" ]
  [[ "$stderr" != *"root not found"* ]]
}
