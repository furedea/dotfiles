# Shared setup for Herdr plugin synchronization tests.

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
export REPO_ROOT

setup_herdr_stub() {
  HERDR_LOG="$BATS_TEST_TMPDIR/herdr_calls.log"
  HERDR_STUB_DIR="$BATS_TEST_TMPDIR/bin"
  HERDR_PLUGIN_SYNC_STATE_FILE="$BATS_TEST_TMPDIR/managed_plugins"
  mkdir -p "$HERDR_STUB_DIR"
  cat >"$HERDR_STUB_DIR/herdr" <<'STUB'
#!/bin/bash
echo "$*" >>"${HERDR_LOG}"

if [[ "$*" == "plugin list --json" ]]; then
  echo "${HERDR_PLUGIN_LIST_JSON}"
fi
STUB
  chmod +x "$HERDR_STUB_DIR/herdr"
  export HERDR_LOG HERDR_PLUGIN_SYNC_STATE_FILE
  export HERDR_PLUGIN_LIST_JSON='{"result":{"plugins":[]}}'
  export PATH="$HERDR_STUB_DIR:$PATH"
}

herdr_calls() {
  cat "$HERDR_LOG" 2>/dev/null || true
}
