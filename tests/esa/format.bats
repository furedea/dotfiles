#!/usr/bin/env bats
# Tests Markdown formatting used for esa posts.

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
}

format_markdown() {
  dprint fmt --config "$REPO_ROOT/dprint/dprint.json" --stdin article.md
}

@test "Markdown formatting preserves line breaks in esa prose" {
  run --separate-stderr format_markdown < <(printf 'こんにちは．\nこんばんは．\n')

  [ "$status" -eq 0 ]
  [ "$output" = $'こんにちは．\nこんばんは．' ]
}

@test "Markdown formatting indents nested lists by four spaces" {
  run --separate-stderr format_markdown < <(printf -- '- parent\n  - child\n')

  [ "$status" -eq 0 ]
  [ "$output" = $'- parent\n    - child' ]
}

@test "Markdown formatting with an explicit config accepts an absolute path outside the config directory" {
  local _outside="$BATS_TEST_TMPDIR/outside/post.md"
  mkdir -p "${_outside%/*}"

  run --separate-stderr dprint fmt --config "$REPO_ROOT/dprint/dprint.json" --stdin "$_outside" < <(printf -- '- parent\n  - child\n')

  [ "$status" -eq 0 ]
  [ "$output" = $'- parent\n    - child' ]
}
