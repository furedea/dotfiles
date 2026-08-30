# Shared setup for Herdr script tests.

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

if [[ "$*" == "plugin install "* ]] && [[ "${HERDR_INSTALL_EXIT_CODE:-0}" -ne 0 ]]; then
  echo "plugin install failed" >&2
  exit "${HERDR_INSTALL_EXIT_CODE}"
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

setup_merge_pull_request_stubs() {
  TEST_REPOSITORY="$BATS_TEST_TMPDIR/repository"
  GH_LOG="$BATS_TEST_TMPDIR/gh_calls.log"
  GIT_LOG="$BATS_TEST_TMPDIR/git_calls.log"
  GH_BIN="$BATS_TEST_TMPDIR/gh"
  GIT_BIN="$BATS_TEST_TMPDIR/git"
  GIT_HEAD="0123456789abcdef0123456789abcdef01234567"
  mkdir -p "$TEST_REPOSITORY"

  cat >"$GH_BIN" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$GH_LOG"

case "$1 $2" in
  "pr view")
    if [[ "${GH_VIEW_EXIT_CODE:-0}" -ne 0 ]]; then
      printf '%s\n' "${GH_VIEW_ERROR:-unable to find pull request}" >&2
      exit "$GH_VIEW_EXIT_CODE"
    fi
    printf '%b\n' "${GH_VIEW_OUTPUT:-42\\tMerge helper\\tmain\\tfeature/test}"
    ;;
  "pr merge")
    if [[ "${GH_MERGE_EXIT_CODE:-0}" -ne 0 ]]; then
      printf '%s\n' "${GH_MERGE_ERROR:-pull request is not mergeable}" >&2
      exit "$GH_MERGE_EXIT_CODE"
    fi
    ;;
esac
STUB

  cat >"$GIT_BIN" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$GIT_LOG"

case "$*" in
  *"rev-parse --show-toplevel")
    if [[ "${GIT_ROOT_EXIT_CODE:-0}" -ne 0 ]]; then
      printf '%s\n' "${GIT_ROOT_ERROR:-not a git repository}" >&2
      exit "$GIT_ROOT_EXIT_CODE"
    fi
    printf '%s\n' "$TEST_REPOSITORY"
    ;;
  *"status --porcelain=v1")
    printf '%b' "${GIT_STATUS_OUTPUT:-}"
    ;;
  *"rev-parse HEAD")
    if [[ "${GIT_HEAD_EXIT_CODE:-0}" -ne 0 ]]; then
      printf '%s\n' "${GIT_HEAD_ERROR:-unable to read HEAD}" >&2
      exit "$GIT_HEAD_EXIT_CODE"
    fi
    printf '%s\n' "$GIT_HEAD"
    ;;
  *"worktree list --porcelain")
    printf '%b' "${GIT_WORKTREE_OUTPUT:-worktree $TEST_REPOSITORY\\nHEAD $GIT_HEAD\\nbranch refs/heads/feature/test\\n}"
    ;;
esac
STUB

  chmod +x "$GH_BIN" "$GIT_BIN"
  export GH_BIN GH_LOG GIT_BIN GIT_HEAD GIT_LOG TEST_REPOSITORY
}

merge_pull_request_gh_calls() {
  cat "$GH_LOG" 2>/dev/null || true
}
