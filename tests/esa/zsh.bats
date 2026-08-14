#!/usr/bin/env bats
# Tests for opening esa posts from Zsh.

setup() {
  load test-helper/setup
  setup_esa_stub
  setup_editor_stub
  setup_fzf_stub
  ESA_ZSH="$REPO_ROOT/zsh/esa.zsh"
}

@test "opening a numbered esa post fetches its body through the official CLI" {
  run zsh -c "source '$ESA_ZSH'; _esa_edit 1515"

  [ "$status" -eq 0 ]
  [ "$(esa_calls)" = "post view 1515 --json body_md" ]
  [[ "$(editor_calls)" == "1515|"*"|# Existing body" ]]

  local marked_file
  marked_file="$(cut -d '|' -f 2 <<<"$(editor_calls)")"
  [ "$marked_file" = "$(cut -d '|' -f 3 <<<"$(editor_calls)")" ]
}

@test "creating a personal esa post opens it as WIP in the editor" {
  run zsh -c "source '$ESA_ZSH'; en 'new note'"

  local expected_calls
  expected_calls=$'post create Members/k-shigyo/new note --wip --message [skip notice] --json number\n'
  expected_calls+="post view 1515 --json body_md"
  [ "$status" -eq 0 ]
  [ "$(esa_calls)" = "$expected_calls" ]
  [[ "$(editor_calls)" == "1515|"*"|# Existing body" ]]
}

@test "opening a named personal esa post resolves its number through the official CLI" {
  run zsh -c "source '$ESA_ZSH'; ee example"

  local expected_calls
  expected_calls=$'post search full_name:"Members/k-shigyo/example" '
  expected_calls+=$'--per-page 100 --json number,name,category,full_name\n'
  expected_calls+="post view 1515 --json body_md"
  [ "$status" -eq 0 ]
  [ "$(esa_calls)" = "$expected_calls" ]
  [[ "$(editor_calls)" == "1515|"*"|# Existing body" ]]
}

@test "selecting a personal esa post opens the chosen search result" {
  run zsh -c "source '$ESA_ZSH'; ee"

  local expected_calls
  expected_calls=$'post search in:"Members/k-shigyo" sort:updated-desc '
  expected_calls+=$'--per-page 100 --json number,full_name\n'
  expected_calls+="post view 1515 --json body_md"
  [ "$status" -eq 0 ]
  [ "$(esa_calls)" = "$expected_calls" ]
  [[ "$(editor_calls)" == "1515|"*"|# Existing body" ]]
}

@test "opening the placement minutes resolves the fixed esa post" {
  run zsh -c "source '$ESA_ZSH'; eep"

  local expected_calls
  expected_calls=$'post search full_name:"議事録/2026年度配属/shigyo" '
  expected_calls+=$'--per-page 100 --json number,name,category,full_name\n'
  expected_calls+="post view 2525 --json body_md"
  [ "$status" -eq 0 ]
  [ "$(esa_calls)" = "$expected_calls" ]
  [[ "$(editor_calls)" == "2525|"*"|# Existing body" ]]
}

@test "shipping the last edited esa post uses its remembered number" {
  run zsh -c "source '$ESA_ZSH'; _ESA_LAST_POST_NUMBER=1515; es"

  [ "$status" -eq 0 ]
  [ "$(esa_calls)" = "post update 1515 --ship" ]
}

@test "quietly shipping an esa post suppresses its notification" {
  run zsh -c "source '$ESA_ZSH'; _ESA_LAST_POST_NUMBER=1515; es --quiet"

  [ "$status" -eq 0 ]
  [ "$(esa_calls)" = "post update 1515 --ship --message [skip notice]" ]
}
