# Shared setup for esa integration tests.

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
export REPO_ROOT

setup_esa_stub() {
  ESA_LOG="$BATS_TEST_TMPDIR/esa_calls.log"
  ESA_STUB_DIR="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$ESA_STUB_DIR"
  cat >"$ESA_STUB_DIR/esa" <<'STUB'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
set +x

printf '%s\n' "$*" >>"${ESA_LOG}"
case "$1 $2" in
"post create")
  printf '{"number":1515,"url":"https://posl.esa.io/posts/1515"}\n'
  ;;
"post search")
  if [[ "$*" == *"議事録/2026年度配属/shigyo"* ]]; then
    cat <<'JSON'
{
  "posts": [
    {
      "number": 2525,
      "name": "shigyo",
      "category": "議事録/2026年度配属",
      "full_name": "議事録/2026年度配属/shigyo"
    }
  ]
}
JSON
  else
    cat <<'JSON'
{
  "posts": [
    {
      "number": 1515,
      "name": "example",
      "category": "Members/k-shigyo",
      "full_name": "Members/k-shigyo/example"
    }
  ]
}
JSON
  fi
  ;;
"post view")
  printf '{"body_md":"# Existing body\\n"}\n'
  ;;
esac
if [[ -n "${ESA_STUB_STDERR:-}" ]]; then
  printf '%s\n' "$ESA_STUB_STDERR" >&2
fi
exit "${ESA_STUB_EXIT_STATUS:-0}"
STUB
  chmod +x "$ESA_STUB_DIR/esa"
  export ESA_LOG
  export PATH="$ESA_STUB_DIR:$PATH"
}

setup_editor_stub() {
  EDITOR_LOG="$BATS_TEST_TMPDIR/editor_calls.log"
  EDITOR_STUB="$BATS_TEST_TMPDIR/esa_test_editor"
  cat >"$EDITOR_STUB" <<'STUB'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
set +x

printf '%s|%s|%s|%s\n' \
  "${ESA_EDIT_POST_NUMBER:-}" \
  "${ESA_EDIT_FILE:-}" \
  "$1" \
  "$(cat "$1")" >>"${EDITOR_LOG}"
STUB
  chmod +x "$EDITOR_STUB"
  export EDITOR="$EDITOR_STUB"
  export EDITOR_LOG
}

setup_fzf_stub() {
  FZF_STUB_DIR="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$FZF_STUB_DIR"
  cat >"$FZF_STUB_DIR/fzf" <<'STUB'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
set +x

head -n 1
STUB
  chmod +x "$FZF_STUB_DIR/fzf"
  export PATH="$FZF_STUB_DIR:$PATH"
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

esa_calls() {
  cat "$ESA_LOG" 2>/dev/null || true
}

editor_calls() {
  cat "$EDITOR_LOG" 2>/dev/null || true
}
