#!/usr/bin/env bats
# Executable specifications for the Herdr pull-request merge helper.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  setup_merge_pull_request_stubs
  SCRIPT="$REPO_ROOT/herdr/merge_pull_request.sh"
}

@test "Enter immediately squash-merges the current PR and deletes safe branches" {
  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<""

  [ "$status" -eq 0 ]
  [[ "$(merge_pull_request_gh_calls)" == *"pr merge --squash --delete-branch --match-head-commit $GIT_HEAD"* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"--auto"* ]]
}

@test "Ctrl+M confirms the pull-request merge" {
  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<$'\r'

  [ "$status" -eq 0 ]
  [[ "$(merge_pull_request_gh_calls)" == *"pr merge --squash"* ]]
}

@test "Escape cancels without merging the pull request" {
  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<$'\e'

  [ "$status" -eq 0 ]
  [[ "$output" == *"Cancelled."* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"pr merge"* ]]
}

@test "Ctrl+C cancels without merging the pull request" {
  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<$'\003'

  [ "$status" -eq 0 ]
  [[ "$output" == *"Cancelled."* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"pr merge"* ]]
}

@test "End of input cancels without merging the pull request" {
  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" </dev/null

  [ "$status" -eq 0 ]
  [[ "$output" == *"Cancelled."* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"pr merge"* ]]
}

@test "A dirty working tree blocks the pull-request merge" {
  export GIT_STATUS_OUTPUT=$' M herdr/config.toml\n'

  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<""

  [ "$status" -ne 0 ]
  [[ "$output" == *"working tree has uncommitted changes"* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"pr merge"* ]]
}

@test "A base branch checked out elsewhere keeps linked-worktree branches" {
  export GIT_WORKTREE_OUTPUT="worktree $TEST_REPOSITORY
HEAD $GIT_HEAD
branch refs/heads/feature/test

worktree $BATS_TEST_TMPDIR/main-repository
HEAD 89abcdef0123456789abcdef0123456789abcdef
branch refs/heads/main
"

  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<""

  [ "$status" -eq 0 ]
  [[ "$(merge_pull_request_gh_calls)" == *"pr merge --squash --match-head-commit $GIT_HEAD"* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"--delete-branch"* ]]
  [[ "$output" == *"Local cleanup: keep this worktree and local branch"* ]]
}

@test "A rejected immediate merge keeps the GitHub error visible" {
  export GH_MERGE_EXIT_CODE=1
  export GH_MERGE_ERROR="required checks have not passed"

  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<$'\n'

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"required checks have not passed"* ]]
  [[ "$output" == *"Press Enter or Esc to close"* ]]
}

@test "A missing pull request keeps the GitHub error visible" {
  export GH_VIEW_EXIT_CODE=1
  export GH_VIEW_ERROR="no pull requests found for branch"

  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<""

  [ "$status" -eq 1 ]
  [[ "$stderr" == *"no pull requests found for branch"* ]]
  [[ "$output" == *"Press Enter or Esc to close"* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"pr merge"* ]]
}

@test "A Git metadata failure remains visible" {
  export GIT_HEAD_EXIT_CODE=128
  export GIT_HEAD_ERROR="unable to resolve HEAD"

  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<$'\e'

  [ "$status" -eq 128 ]
  [[ "$stderr" == *"unable to resolve HEAD"* ]]
  [[ "$output" == *"Press Enter or Esc to close"* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"pr merge"* ]]
}

@test "An unexpected confirmation key cancels and consumes the following Enter" {
  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<$'x'

  [ "$status" -eq 0 ]
  [[ "$output" == *"Cancelled."* ]]
  [[ "$output" == *"Press Enter or Esc to close"* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"pr merge"* ]]
}

@test "The confirmation identifies the pull request and branch direction" {
  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<$'\e'

  [ "$status" -eq 0 ]
  [[ "$output" == *"PR #42: Merge helper"* ]]
  [[ "$output" == *"feature/test -> main"* ]]
  [[ "$output" == *"Enter / Ctrl+M  Squash and merge now"* ]]
}

@test "An invalid repository keeps the Git error visible" {
  export GIT_ROOT_EXIT_CODE=128
  export GIT_ROOT_ERROR="not a git repository"

  run --separate-stderr bash "$SCRIPT" "$TEST_REPOSITORY" <<<""

  [ "$status" -eq 128 ]
  [[ "$stderr" == *"not a git repository"* ]]
  [[ "$output" == *"Press Enter or Esc to close"* ]]
  ! [[ "$(merge_pull_request_gh_calls)" == *"pr view"* ]]
}
