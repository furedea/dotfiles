# Shared setup for Herdr plugin synchronization tests.

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
export REPO_ROOT

setup_herdr_stub() {
  HERDR_LOG="$BATS_TEST_TMPDIR/herdr_calls.log"
  HERDR_STUB_DIR="$BATS_TEST_TMPDIR/bin"
  HERDR_PLUGIN_SYNC_STATE_FILE="$BATS_TEST_TMPDIR/managed_plugins"
  mkdir -p "$HERDR_STUB_DIR"
  cat >"$HERDR_STUB_DIR/herdr" <<'STUB'
#!/usr/bin/env bash
echo "$*" >>"${HERDR_LOG}"

if [[ "$*" == "plugin list --json" ]]; then
  echo "${HERDR_PLUGIN_LIST_JSON}"
fi

if [[ "$*" == "plugin install "* ]] && [[ -n "${HERDR_INSTALL_STATE_LOG:-}" ]]; then
  cat "${HERDR_PLUGIN_SYNC_STATE_FILE}" >>"${HERDR_INSTALL_STATE_LOG}"
fi

if [[ -n "${HERDR_FAIL_INSTALL_SOURCE:-}" ]] &&
  [[ "$*" == "plugin install ${HERDR_FAIL_INSTALL_SOURCE} "* ]]; then
  exit "${HERDR_INSTALL_FAILURE_STATUS:-23}"
fi
STUB
  chmod +x "$HERDR_STUB_DIR/herdr"
  export HERDR_LOG HERDR_PLUGIN_SYNC_STATE_FILE
  export HERDR_PLUGIN_LIST_JSON='{"result":{"plugins":[]}}'
  unset HERDR_FAIL_INSTALL_SOURCE HERDR_INSTALL_FAILURE_STATUS HERDR_INSTALL_STATE_LOG
  export PATH="$HERDR_STUB_DIR:$PATH"
}

herdr_calls() {
  cat "$HERDR_LOG" 2>/dev/null || true
}
