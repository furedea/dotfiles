#!/usr/bin/env bats
# Tests for saving esa posts from Neovim.

setup() {
  load test-helper/setup
  setup_kasa_stub
  setup_nvim_data_stub
  ARTICLE_FILE="$BATS_TEST_TMPDIR/article.md"
  printf '# Before\n' >"$ARTICLE_FILE"
}

@test "the Neovim configuration enables WIP saves for marked esa buffers" {
  run env \
    ESA_EDIT_POST="Members/k-shigyo/example" \
    ESA_EDIT_POST_NUMBER=1515 \
    ESA_EDIT_FILE="$ARTICLE_FILE" \
    XDG_DATA_HOME="$NVIM_DATA_HOME" \
    nvim --headless -u "$REPO_ROOT/nvim/init.lua" \
    "$ARTICLE_FILE" \
    -c "call setline(1, '# After')" \
    -c write \
    -c quit

  [ "$status" -eq 0 ]
  [ "$(kasa_calls)" = "post //1515 --body $ARTICLE_FILE --wip --no-notice" ]
}

@test "saving another buffer in an esa editing session does not invoke kasa" {
  local other_file="$BATS_TEST_TMPDIR/other.md"
  printf '# Other\n' >"$other_file"

  run env \
    ESA_EDIT_POST="Members/k-shigyo/example" \
    ESA_EDIT_POST_NUMBER=1515 \
    ESA_EDIT_FILE="$ARTICLE_FILE" \
    XDG_DATA_HOME="$NVIM_DATA_HOME" \
    nvim --headless -u "$REPO_ROOT/nvim/init.lua" \
    "$other_file" \
    -c "call setline(1, '# Changed')" \
    -c write \
    -c quit

  [ "$status" -eq 0 ]
  [ -z "$(kasa_calls)" ]
}

@test "saving an esa buffer updates the existing post number as WIP without notice" {
  run env \
    ESA_EDIT_POST="Members/k-shigyo/example" \
    ESA_EDIT_POST_NUMBER=1515 \
    ESA_EDIT_FILE="$ARTICLE_FILE" \
    nvim --headless -u NONE \
    --cmd "set runtimepath^=$REPO_ROOT/nvim" \
    "$ARTICLE_FILE" \
    -c "lua require('esa').setup()" \
    -c "call setline(1, '# After')" \
    -c write \
    -c quit

  [ "$status" -eq 0 ]
  [ "$(kasa_calls)" = "post //1515 --body $ARTICLE_FILE --wip --no-notice" ]
  [ "$(cat "$ARTICLE_FILE")" = "# After" ]
}

@test "a failed esa WIP save reports the kasa error" {
  run env \
    ESA_EDIT_POST="Members/k-shigyo/example" \
    ESA_EDIT_POST_NUMBER=1515 \
    ESA_EDIT_FILE="$ARTICLE_FILE" \
    KASA_EXIT_STATUS=1 \
    KASA_STDERR="kasa: error: request rejected" \
    nvim --headless -u NONE \
    --cmd "set runtimepath^=$REPO_ROOT/nvim" \
    "$ARTICLE_FILE" \
    -c "lua require('esa').setup()" \
    -c write \
    -c "quit!"

  [ "$status" -eq 0 ]
  [[ "$output" == *"kasa: error: request rejected"* ]]
}

@test "a failed esa WIP save prevents wq from discarding the modified buffer" {
  run env \
    ESA_EDIT_POST="Members/k-shigyo/example" \
    ESA_EDIT_POST_NUMBER=1515 \
    ESA_EDIT_FILE="$ARTICLE_FILE" \
    KASA_EXIT_STATUS=1 \
    nvim --headless -u NONE \
    --cmd "set runtimepath^=$REPO_ROOT/nvim" \
    "$ARTICLE_FILE" \
    -c "lua require('esa').setup()" \
    -c "call setline(1, '# After')" \
    -c wq \
    -c "lua vim.wait(50)" \
    -c "lua print('MODIFIED=' .. tostring(vim.bo.modified))" \
    -c "quit!"

  [ "$status" -eq 0 ]
  [[ "$output" == *"MODIFIED=true"* ]]
}
