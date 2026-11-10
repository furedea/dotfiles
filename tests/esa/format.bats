#!/usr/bin/env bats
# Tests Markdown formatting used for esa posts.

setup() {
  load test-helper/setup
}

format_markdown() {
  dprint fmt --config "$REPO_ROOT/dprint/dprint.json" --stdin article.md
}

@test "Markdown formatting preserves line breaks in esa prose" {
  run format_markdown < <(printf 'こんにちは．\nこんばんは．\n')

  [ "$status" -eq 0 ]
  [ "$output" = $'こんにちは．\nこんばんは．' ]
}

@test "Markdown formatting indents nested lists by four spaces" {
  run format_markdown < <(printf -- '- parent\n  - child\n')

  [ "$status" -eq 0 ]
  [ "$output" = $'- parent\n    - child' ]
}
