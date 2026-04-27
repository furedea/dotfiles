#!/usr/bin/env bats
# Tests for github/setup_repo.sh

setup() {
  load test_helper/setup
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

# --- Create path (no existing ruleset) ---

@test "applies settings and creates ruleset for a new repo" {
  run bash "$SCRIPT" "owner/myrepo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Applied repo settings to owner/myrepo"* ]]
  [[ "$output" == *"Created ruleset on owner/myrepo"* ]]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"repos/owner/myrepo -X PATCH --input"*"repo_settings.json"* ]]
  [[ "$calls" == *"repos/owner/myrepo/rulesets -X POST --input"*"ruleset.json"* ]]
}

@test "gh api is called 3 times when creating a new ruleset" {
  run bash "$SCRIPT" "owner/myrepo"
  [ "$status" -eq 0 ]
  [ "$(gh_call_count)" -eq 3 ]
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
