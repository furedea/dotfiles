#!/usr/bin/env bats
# Tests for github/configure_repo.sh

setup() {
  load test-helper/setup
  setup_gh_stub
}

# --- Usage ---

@test "shows usage with --help" {
  run bash "$SCRIPT" --help
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "shows usage with -h" {
  run bash "$SCRIPT" -h
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "shows usage when no argument is given" {
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
}

@test "rejects multiple repository arguments" {
  run bash "$SCRIPT" "owner/first" "owner/second"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
  ! grep -q "repos/owner/" "$GH_LOG"
}

@test "rejects unknown options" {
  run bash "$SCRIPT" --unknown
  [ "$status" -eq 1 ]
  [[ "$output" == *"Usage:"* ]]
  ! grep -q "repos/" "$GH_LOG"
}

@test "configures the authenticated owner's repository when given a short name" {
  run bash "$SCRIPT" "myrepo"
  [ "$status" -eq 0 ]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"api user --jq .login"* ]]
  [[ "$calls" == *"repos/furedea/myrepo -X PATCH --input"* ]]
}

# --- Create path (no existing ruleset) ---

@test "applies settings and creates ruleset for a new repo" {
  run bash "$SCRIPT" "owner/myrepo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Applied repo settings to owner/myrepo"* ]]
  [[ "$output" == *"Created ruleset on owner/myrepo"* ]]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"repos/owner/myrepo -X PATCH --input"*"repo_settings.json"* ]]
  [[ "$calls" == *"repos/owner/myrepo/vulnerability-alerts -X PUT"* ]]
  [[ "$calls" == *"repos/owner/myrepo/rulesets -X POST --input"*"ruleset.json"* ]]
}

# --- Update path (existing ruleset, idempotent) ---

@test "updates existing ruleset by id when one with the same name exists" {
  setup_gh_stub_with_existing_ruleset 42
  run bash "$SCRIPT" "owner/myrepo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Updated ruleset 42 on owner/myrepo"* ]]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"repos/owner/myrepo/rulesets/42 -X PUT --input"*"ruleset.json"* ]]
}
