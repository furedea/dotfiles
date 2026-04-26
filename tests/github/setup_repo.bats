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

# --- Explicit repo argument ---

@test "applies settings and base ruleset to explicit repo" {
  run bash "$SCRIPT" "owner/myrepo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Applied repo settings to owner/myrepo"* ]]
  [[ "$output" == *"Applied base ruleset to owner/myrepo"* ]]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"repos/owner/myrepo -X PATCH --input"*"repo_settings.json"* ]]
  [[ "$calls" == *"repos/owner/myrepo/rulesets -X POST --input"*"ruleset_base.json"* ]]
}

@test "gh api called exactly twice without --template" {
  run bash "$SCRIPT" "owner/myrepo"
  [ "$status" -eq 0 ]
  [ "$(gh_call_count)" -eq 2 ]
}

# --- Auto-detect repo ---

@test "detects repo via gh repo view when no argument given" {
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Applied repo settings to detected/repo"* ]]
  [[ "$output" == *"Applied base ruleset to detected/repo"* ]]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"repo view --json nameWithOwner"* ]]
}

# --- Language-specific rulesets ---

@test "--template python applies python ruleset" {
  run bash "$SCRIPT" -t python "owner/myrepo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Applied python ruleset to owner/myrepo"* ]]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"ruleset_python.json"* ]]
}

@test "--template typescript applies typescript ruleset" {
  run bash "$SCRIPT" --template typescript "owner/myrepo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Applied typescript ruleset to owner/myrepo"* ]]

  local calls
  calls="$(gh_calls)"
  [[ "$calls" == *"ruleset_typescript.json"* ]]
}

@test "--template rust applies rust ruleset" {
  run bash "$SCRIPT" -t rust "owner/myrepo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Applied rust ruleset to owner/myrepo"* ]]
}

@test "--template tex applies tex ruleset" {
  run bash "$SCRIPT" -t tex "owner/myrepo"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Applied tex ruleset to owner/myrepo"* ]]
}

@test "gh api called 3 times with --template" {
  run bash "$SCRIPT" -t python "owner/myrepo"
  [ "$status" -eq 0 ]
  [ "$(gh_call_count)" -eq 3 ]
}

# --- Error cases ---

@test "fails for unknown language template" {
  run bash "$SCRIPT" -t golang "owner/myrepo"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Unknown language: golang"* ]]
}
