#!/usr/bin/env bats
# Tests for opening esa posts from Zsh.

setup() {
  load test-helper/setup
  setup_kasa_stub
  setup_editor_stub
  ESA_ZSH="$REPO_ROOT/zsh/esa.zsh"
}

@test "opening an esa post marks only its temporary buffer for WIP saves" {
  run zsh -c "source '$ESA_ZSH'; _esa_edit 'Members/k-shigyo/example'"

  [ "$status" -eq 0 ]
  [ "$(kasa_calls)" = $'info Members/k-shigyo/example\ncat Members/k-shigyo/example' ]
  [[ "$(editor_calls)" == "Members/k-shigyo/example|1515|"*"|# Existing body" ]]

  local marked_file
  marked_file="$(cut -d '|' -f 3 <<<"$(editor_calls)")"
  [ "$marked_file" = "$(cut -d '|' -f 4 <<<"$(editor_calls)")" ]
}
