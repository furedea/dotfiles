#!/usr/bin/env bats
# Tests for github/repo.sh.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$GITHUB_DIR/repo.sh"
  setup_create_repo_stubs
}

@test "creates a repository through the public command" {
  run --separate-stderr bash "$SCRIPT" create agent-harness --private
  [ "$status" -eq 0 ]
  [ "$output" = "$BATS_TEST_TMPDIR/ghq/github.com/furedea/agent-harness" ]
  [[ "$stderr" != +* ]]
  [[ "$stderr" != *$'\n+'* ]]
}

@test "configures a repository through the public command" {
  run --separate-stderr bash "$SCRIPT" configure agent-harness
  [ "$status" -eq 0 ]
  [[ "$stderr" != +* ]]
  [[ "$stderr" != *$'\n+'* ]]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"repos/furedea/agent-harness -X PATCH --input"* ]]
}

@test "synchronizes owned repositories through the public command" {
  run --separate-stderr bash "$SCRIPT" sync --dry-run

  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$stderr" >&2
  fi
  [ "$status" -eq 0 ]
  [[ "$(gh_calls)" == *"repo list furedea"* ]]
}

@test "shows top-level help with --help" {
  run bash "$SCRIPT" --help
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
  [[ "$output" == *"repo <command> [arguments]"* ]]
  [[ "$output" == *"create"* ]]
  [[ "$output" == *"configure"* ]]
  [[ "$output" == *"sync"* ]]
}

@test "does not print the Bash execution trace" {
  run --separate-stderr bash "$SCRIPT" --help
  [ "$status" -eq 1 ]
  [[ "$stderr" != +* ]]
  [[ "$stderr" != *$'\n+'* ]]
}

@test "shows top-level help with -h" {
  run bash "$SCRIPT" -h
  [ "$status" -eq 1 ]
  [[ "$output" == *"repo <command> [arguments]"* ]]
}

@test "shows create-specific help" {
  run bash "$SCRIPT" create --help
  [ "$status" -eq 1 ]
  [[ "$output" == *"repo create <name-or-owner/name> <visibility> [options]"* ]]
  [[ "$output" == *"--template"* ]]
  [[ "$output" == *"--private"* ]]
  [[ "$output" == *"--clone"* ]]
}

@test "shows configure-specific help" {
  run bash "$SCRIPT" configure --help
  [ "$status" -eq 1 ]
  [[ "$output" == *"repo configure <name-or-owner/name>"* ]]
}
