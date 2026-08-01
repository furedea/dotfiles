# Shared setup for esa integration tests.

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
export REPO_ROOT

setup_kasa_stub() {
  KASA_LOG="$BATS_TEST_TMPDIR/kasa_calls.log"
  KASA_STUB_DIR="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$KASA_STUB_DIR"
  cat >"$KASA_STUB_DIR/kasa" <<'STUB'
#!/bin/bash
echo "$*" >>"${KASA_LOG}"
case "$1" in
info)
  printf '{"number":1515}\n'
  ;;
cat)
  printf '# Existing body\n'
  ;;
esac
if [[ -n "${KASA_STDERR:-}" ]]; then
  printf '%s\n' "$KASA_STDERR" >&2
fi
exit "${KASA_EXIT_STATUS:-0}"
STUB
  chmod +x "$KASA_STUB_DIR/kasa"
  export KASA_LOG
  export PATH="$KASA_STUB_DIR:$PATH"
}

setup_editor_stub() {
  EDITOR_LOG="$BATS_TEST_TMPDIR/editor_calls.log"
  EDITOR_STUB="$BATS_TEST_TMPDIR/esa_test_editor"
  cat >"$EDITOR_STUB" <<'STUB'
#!/bin/bash
printf '%s|%s|%s|%s|%s\n' \
  "${ESA_EDIT_POST:-}" \
  "${ESA_EDIT_POST_NUMBER:-}" \
  "${ESA_EDIT_FILE:-}" \
  "$1" \
  "$(cat "$1")" >>"${EDITOR_LOG}"
STUB
  chmod +x "$EDITOR_STUB"
  export EDITOR="$EDITOR_STUB"
  export EDITOR_LOG
}

setup_nvim_data_stub() {
  NVIM_DATA_HOME="$BATS_TEST_TMPDIR/data"
  local _lazy_dir="$NVIM_DATA_HOME/nvim/lazy/lazy.nvim/lua"
  mkdir -p "$_lazy_dir"
  cat >"$_lazy_dir/lazy.lua" <<'STUB'
return {
  setup = function() end,
}
STUB
  export NVIM_DATA_HOME
}

kasa_calls() {
  cat "$KASA_LOG" 2>/dev/null || true
}

editor_calls() {
  cat "$EDITOR_LOG" 2>/dev/null || true
}
