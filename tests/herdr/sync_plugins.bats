#!/usr/bin/env bats
# Tests for herdr/sync_plugins.sh

bats_require_minimum_version 1.5.0

setup() {
  load test-helper/setup
  SCRIPT="$REPO_ROOT/herdr/sync_plugins.sh"
  setup_herdr_stub
}

@test "installs a missing plugin at the declared commit" {
  run bash "$SCRIPT" \
    persiyanov.reviewr \
    persiyanov/herdr-reviewr \
    160ad607a195ee35ac9450e887974b3b5ddc4479

  [ "$status" -eq 0 ]
  [[ "$(herdr_calls)" == *"plugin install persiyanov/herdr-reviewr --ref 160ad607a195ee35ac9450e887974b3b5ddc4479 --yes"* ]]
  [ "$(cat "$HERDR_PLUGIN_SYNC_STATE_FILE")" = "persiyanov.reviewr" ]
}

@test "keeps a plugin installed at the declared commit" {
  export HERDR_PLUGIN_LIST_JSON='{"result":{"plugins":[{"plugin_id":"persiyanov.reviewr","source":{"resolved_commit":"160ad607a195ee35ac9450e887974b3b5ddc4479"}}]}}'

  run bash "$SCRIPT" \
    persiyanov.reviewr \
    persiyanov/herdr-reviewr \
    160ad607a195ee35ac9450e887974b3b5ddc4479

  [ "$status" -eq 0 ]
  ! [[ "$(herdr_calls)" == *"plugin install"* ]]
}

@test "stays quiet when plugins already match the declaration" {
  export HERDR_PLUGIN_LIST_JSON='{"result":{"plugins":[{"plugin_id":"persiyanov.reviewr","source":{"resolved_commit":"160ad607a195ee35ac9450e887974b3b5ddc4479"}}]}}'

  run bash -c 'exec 9>/dev/null; BASH_XTRACEFD=9 bash "$@"' _ "$SCRIPT" \
    persiyanov.reviewr \
    persiyanov/herdr-reviewr \
    160ad607a195ee35ac9450e887974b3b5ddc4479

  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "uninstalls a previously managed plugin removed from the declaration" {
  echo "persiyanov.reviewr" >"$HERDR_PLUGIN_SYNC_STATE_FILE"
  export HERDR_PLUGIN_LIST_JSON='{"result":{"plugins":[{"plugin_id":"persiyanov.reviewr","source":{"resolved_commit":"160ad607a195ee35ac9450e887974b3b5ddc4479"}}]}}'

  run bash "$SCRIPT"

  [ "$status" -eq 0 ]
  [[ "$(herdr_calls)" == *"plugin uninstall persiyanov.reviewr"* ]]
  [ ! -s "$HERDR_PLUGIN_SYNC_STATE_FILE" ]
}

@test "returns a failure when a declared plugin cannot be installed" {
  export HERDR_FAIL_INSTALL_SOURCE="persiyanov/herdr-reviewr"

  run bash "$SCRIPT" \
    persiyanov.reviewr \
    persiyanov/herdr-reviewr \
    160ad607a195ee35ac9450e887974b3b5ddc4479

  [ "$status" -eq 23 ]
}

@test "preserves the managed state when a declared plugin cannot be installed" {
  printf '%s\n' "previous.plugin" >"$HERDR_PLUGIN_SYNC_STATE_FILE"
  export HERDR_FAIL_INSTALL_SOURCE="persiyanov/herdr-reviewr"

  run bash "$SCRIPT" \
    persiyanov.reviewr \
    persiyanov/herdr-reviewr \
    160ad607a195ee35ac9450e887974b3b5ddc4479

  [ "$status" -ne 0 ]
  [ "$(cat "$HERDR_PLUGIN_SYNC_STATE_FILE")" = "previous.plugin" ]
}

@test "replaces the managed state after every declared plugin is installed" {
  printf '%s\n' "previous.plugin" >"$HERDR_PLUGIN_SYNC_STATE_FILE"
  export HERDR_INSTALL_STATE_LOG="$BATS_TEST_TMPDIR/install_state.log"

  run bash "$SCRIPT" \
    persiyanov.reviewr \
    persiyanov/herdr-reviewr \
    160ad607a195ee35ac9450e887974b3b5ddc4479 \
    example.second \
    example/herdr-second \
    0123456789abcdef

  [ "$status" -eq 0 ]
  [ "$(cat "$HERDR_INSTALL_STATE_LOG")" = $'previous.plugin\nprevious.plugin' ]
  [ "$(cat "$HERDR_PLUGIN_SYNC_STATE_FILE")" = $'persiyanov.reviewr\nexample.second' ]
}

@test "reports the declared plugin that could not be installed" {
  export HERDR_FAIL_INSTALL_SOURCE="persiyanov/herdr-reviewr"

  run bash "$SCRIPT" \
    persiyanov.reviewr \
    persiyanov/herdr-reviewr \
    160ad607a195ee35ac9450e887974b3b5ddc4479

  [ "$status" -ne 0 ]
  [[ "$output" == *"Failed to synchronize Herdr plugin:"* ]]
  [[ "$output" == *"id: persiyanov.reviewr"* ]]
  [[ "$output" == *"source: persiyanov/herdr-reviewr"* ]]
  [[ "$output" == *"ref: 160ad607a195ee35ac9450e887974b3b5ddc4479"* ]]
}

@test "keeps removed plugins installed until every declaration is synchronized" {
  printf '%s\n' "previous.plugin" >"$HERDR_PLUGIN_SYNC_STATE_FILE"
  export HERDR_PLUGIN_LIST_JSON='{"result":{"plugins":[{"plugin_id":"previous.plugin","source":{"resolved_commit":"abcdef"}}]}}'
  export HERDR_FAIL_INSTALL_SOURCE="persiyanov/herdr-reviewr"

  run bash "$SCRIPT" \
    persiyanov.reviewr \
    persiyanov/herdr-reviewr \
    160ad607a195ee35ac9450e887974b3b5ddc4479

  [ "$status" -ne 0 ]
  ! [[ "$(herdr_calls)" == *"plugin uninstall previous.plugin"* ]]
}
