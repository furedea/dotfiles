#!/usr/bin/env bats
# Tests for saving esa posts from Neovim.

setup() {
  load test-helper/setup
  setup_esa_stub
  setup_nvim_data_stub
  ARTICLE_FILE="$BATS_TEST_TMPDIR/article.md"
  printf '# Before\n' >"$ARTICLE_FILE"
}

@test "the Neovim configuration saves marked esa buffers through the official CLI" {
  run env \
    ESA_EDIT_POST_NUMBER=1515 \
    ESA_EDIT_FILE="$ARTICLE_FILE" \
    XDG_DATA_HOME="$NVIM_DATA_HOME" \
    nvim --headless -u "$REPO_ROOT/nvim/init.lua" \
    "$ARTICLE_FILE" \
    -c "call setline(1, '# After')" \
    -c write \
    -c quit

  [ "$status" -eq 0 ]
  [ "$(esa_calls)" = "post update 1515 --body-file $ARTICLE_FILE --wip --message [skip notice]" ]
}

@test "saving another buffer in an esa editing session does not invoke esa CLI" {
  local other_file="$BATS_TEST_TMPDIR/other.md"
  printf '# Other\n' >"$other_file"

  run env \
    ESA_EDIT_POST_NUMBER=1515 \
    ESA_EDIT_FILE="$ARTICLE_FILE" \
    XDG_DATA_HOME="$NVIM_DATA_HOME" \
    nvim --headless -u "$REPO_ROOT/nvim/init.lua" \
    "$other_file" \
    -c "call setline(1, '# Changed')" \
    -c write \
    -c quit

  [ "$status" -eq 0 ]
  [ -z "$(esa_calls)" ]
}

@test "saving an esa buffer updates the existing post as WIP without notice" {
  run env \
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
  [ "$(esa_calls)" = "post update 1515 --body-file $ARTICLE_FILE --wip --message [skip notice]" ]
  [ "$(cat "$ARTICLE_FILE")" = "# After" ]
}

@test "a failed esa WIP save reports the official CLI error" {
  run env \
    ESA_EDIT_POST_NUMBER=1515 \
    ESA_EDIT_FILE="$ARTICLE_FILE" \
    ESA_STUB_EXIT_STATUS=1 \
    ESA_STUB_STDERR="esa: error: request rejected" \
    nvim --headless -u NONE \
    --cmd "set runtimepath^=$REPO_ROOT/nvim" \
    "$ARTICLE_FILE" \
    -c "lua require('esa').setup()" \
    -c write \
    -c "quit!"

  [ "$status" -eq 0 ]
  [[ "$output" == *"esa: error: request rejected"* ]]
}

@test "a failed esa WIP save prevents wq from discarding the modified buffer" {
  run env \
    ESA_EDIT_POST_NUMBER=1515 \
    ESA_EDIT_FILE="$ARTICLE_FILE" \
    ESA_STUB_EXIT_STATUS=1 \
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
