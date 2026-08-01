#!/usr/bin/env bats
# Tests Markdown formatting used for esa posts.

setup() {
  load test-helper/setup
  ARTICLE_FILE="$BATS_TEST_TMPDIR/article.md"
  printf 'こんにちは．\nこんばんは．\n' >"$ARTICLE_FILE"
}

@test "Markdown formatting preserves line breaks in esa prose" {
  local _input
  _input="$(cat "$ARTICLE_FILE")"

  run env \
    TMPDIR="$BATS_TEST_TMPDIR" \
    PRETTIERD_DEFAULT_CONFIG="$REPO_ROOT/prettier/.prettierrc" \
    prettierd "$ARTICLE_FILE" <<<"$_input"

  [ "$status" -eq 0 ]
  [ "$output" = $'こんにちは．\nこんばんは．' ]
}
