#!/usr/bin/env bats
# Tests for opening esa posts from Zsh.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  setup_esa_stub
  setup_editor_stub
  setup_fzf_stub
  ESA_ZSH="$REPO_ROOT/zsh/esa.zsh"
}

@test "en displays help for its help options" {
  local _expected
  _expected=$(cat <<'EOF'
Usage: en <title>

Create a WIP post under Members/k-shigyo and edit it in Neovim.

Options:
  -h, --help  Show this help
EOF
  )

  local _option
  for _option in -h --help; do
    run zsh -c "source '$ESA_ZSH'; en '$_option'"

    [ "$status" -eq 0 ]
    [ "$output" = "$_expected" ]
    [ -z "$(esa_calls)" ]
  done
}

@test "en rejects invalid argument counts with usage" {
  local _arguments
  for _arguments in "" "one two"; do
    run --separate-stderr zsh -c "source '$ESA_ZSH'; en $_arguments"

    [ "$status" -eq 1 ]
    [ -z "$output" ]
    [[ "$stderr" == "Usage: en <title>"$'\n'* ]]
    [ -z "$(esa_calls)" ]
  done
}

@test "en rejects an empty title with usage" {
  run --separate-stderr zsh -c "source '$ESA_ZSH'; en ''"

  [ "$status" -eq 1 ]
  [ -z "$output" ]
  [[ "$stderr" == "Usage: en <title>"$'\n'* ]]
  [ -z "$(esa_calls)" ]
}

@test "ee displays help for its help options" {
  local _expected
  _expected=$(cat <<'EOF'
Usage: ee [title]

Open an existing post under Members/k-shigyo.
Without a title, choose one with fzf.

Options:
  -h, --help  Show this help
EOF
  )

  local _option
  for _option in -h --help; do
    run zsh -c "source '$ESA_ZSH'; ee '$_option'"

    [ "$status" -eq 0 ]
    [ "$output" = "$_expected" ]
    [ -z "$(esa_calls)" ]
  done
}

@test "ee rejects extra arguments with usage" {
  run --separate-stderr zsh -c "source '$ESA_ZSH'; ee one two"

  [ "$status" -eq 1 ]
  [ -z "$output" ]
  [[ "$stderr" == "Usage: ee [title]"$'\n'* ]]
  [ -z "$(esa_calls)" ]
}

@test "eep displays help for its help options" {
  local _expected
  _expected=$(cat <<'EOF'
Usage: eep

Open 議事録/2026年度配属/shigyo in Neovim.

Options:
  -h, --help  Show this help
EOF
  )

  local _option
  for _option in -h --help; do
    run zsh -c "source '$ESA_ZSH'; eep '$_option'"

    [ "$status" -eq 0 ]
    [ "$output" = "$_expected" ]
    [ -z "$(esa_calls)" ]
  done
}

@test "eep rejects unexpected arguments with usage" {
  run --separate-stderr zsh -c "source '$ESA_ZSH'; eep unexpected"

  [ "$status" -eq 1 ]
  [ -z "$output" ]
  [[ "$stderr" == "Usage: eep"$'\n'* ]]
  [ -z "$(esa_calls)" ]
}

@test "es displays help for its help options" {
  local _expected
  _expected=$(cat <<'EOF'
Usage: es [-q|--quiet]

Ship the last post opened by en, ee, or eep.

Options:
  -q, --quiet, --no-notice  Ship without notification
  -h, --help                Show this help
EOF
  )

  local _option
  for _option in -h --help; do
    run zsh -c "source '$ESA_ZSH'; es '$_option'"

    [ "$status" -eq 0 ]
    [ "$output" = "$_expected" ]
    [ -z "$(esa_calls)" ]
  done
}

@test "es rejects invalid options with usage" {
  local _arguments
  for _arguments in "--unknown" "--quiet unexpected"; do
    run --separate-stderr zsh -c "source '$ESA_ZSH'; es $_arguments"

    [ "$status" -eq 1 ]
    [ -z "$output" ]
    [[ "$stderr" == "Usage: es [-q|--quiet]"$'\n'* ]]
    [ -z "$(esa_calls)" ]
  done
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
