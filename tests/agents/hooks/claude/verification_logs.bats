#!/usr/bin/env bats
# Retention touches only completed logs owned by this worktree and format.

setup() {
  load test-helper/setup
  export RUN_RELATED_TESTS_REUSE=0
  export XDG_STATE_HOME="$BATS_TEST_TMPDIR/state"
  # Load reporting functions without executing the repository gate.
  # shellcheck disable=SC1090
  source <(sed '/^# Must be inside a Git repository/,$d' "$HOOK_DIR/run_related_tests.sh")
  BASE="$BATS_TEST_TMPDIR/logs"
  mkdir -p "$BASE"
}

completed_log() {
  local _name="$1" _time="$2"
  mkdir -p "$BASE/$_name"
  printf '%s\n' "$_time" >"$BASE/$_name/.complete"
  printf 'failure details\n' >"$BASE/$_name/1.output.log"
}

@test "retention removes expired completed failures but preserves active and legacy logs" {
  completed_log failure-1-old 1
  completed_log failure-2-recent "$(date +%s)"
  mkdir -p "$BASE/failure-3-active" "$BASE/run.legacy"

  prune_failure_logs "$BASE"

  [ ! -e "$BASE/failure-1-old" ]
  [ -d "$BASE/failure-2-recent" ]
  [ -d "$BASE/failure-3-active" ]
  [ -d "$BASE/run.legacy" ]
}

@test "retention preserves symlinks and directories with unrecognized contents" {
  completed_log failure-1-custom 1
  touch "$BASE/failure-1-custom/user.txt"
  mkdir -p "$BATS_TEST_TMPDIR/outside"
  printf '1\n' >"$BATS_TEST_TMPDIR/outside/.complete"
  ln -s "$BATS_TEST_TMPDIR/outside" "$BASE/failure-2-link"

  prune_failure_logs "$BASE"

  [ -f "$BASE/failure-1-custom/user.txt" ]
  [ -f "$BATS_TEST_TMPDIR/outside/.complete" ]
  [ -L "$BASE/failure-2-link" ]
}

@test "retention enforces the completed log budget newest first" {
  completed_log failure-1-old "$(date +%s)"
  completed_log failure-2-new "$(date +%s)"
  # Stub measured sizes; no large test artifacts are needed.
  du() { printf '60000\t%s\n' "$2"; }

  prune_failure_logs "$BASE"

  [ ! -d "$BASE/failure-1-old" ]
  [ -d "$BASE/failure-2-new" ]
}

@test "failure logs separate same-named worktrees by canonical path" {
  mkdir -p "$BATS_TEST_TMPDIR/one/project" "$BATS_TEST_TMPDIR/two/project"
  GIT_ROOT="$BATS_TEST_TMPDIR/one/project"
  prepare_log_directory
  local _first="$LOG_DIRECTORY"
  # shellcheck disable=SC2034 # Read by the sourced reporting function.
  LOG_ATTEMPTED=0
  GIT_ROOT="$BATS_TEST_TMPDIR/two/project"
  prepare_log_directory

  [ "${_first%/*}" != "${LOG_DIRECTORY%/*}" ]
  [[ "$_first" == *'/project-'*'/failure-'* ]]
}

@test "a failed verification reports its command and private details" {
  GIT_ROOT="$BATS_TEST_TMPDIR/project"
  mkdir -p "$GIT_ROOT"
  append_result pytest failed '1 file' 'pytest tests/test_example.py' 'assertion failed'

  [[ "$ERRORS" == *'Command: pytest tests/test_example.py'* ]]
  [ -f "$LOG_DIRECTORY/1.command.log" ]
  [ -f "$LOG_DIRECTORY/1.output.log" ]
  [ "$(cat "$LOG_DIRECTORY/1.output.log")" = 'assertion failed' ]
}

@test "oversized failure output is bounded and explicitly marked as truncated" {
  GIT_ROOT="$BATS_TEST_TMPDIR/project"
  mkdir -p "$GIT_ROOT"
  local _output
  printf -v _output '%*s' "$((LOG_OUTPUT_LIMIT_BYTES + 100))" ''
  _output+='last failure'

  append_result pytest failed '1 file' 'pytest' "$_output"

  [[ "$(head -n 1 "$LOG_DIRECTORY/1.output.log")" == '[Output truncated;'* ]]
  [[ "$(tail -c 20 "$LOG_DIRECTORY/1.output.log")" == *'last failure'* ]]
  [ "$(wc -c <"$LOG_DIRECTORY/1.output.log")" -lt "$((LOG_OUTPUT_LIMIT_BYTES + 100))" ]
}
