REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
export REPO_ROOT
# Keep bsdtar from adding AppleDouble entries to fixture archives.
export COPYFILE_DISABLE=1

# Offline stand-ins for the release downloads and installers used by
# scripts/agents/install_server.sh. Every fixture lives under BATS_TEST_TMPDIR.
function create_install_server_fixtures() {
  HOME_DIR="$BATS_TEST_TMPDIR/home"
  # shellcheck disable=SC2034  # asserted by the .bats file
  BIN_DIR="$HOME_DIR/.local/bin"
  RELEASES="$BATS_TEST_TMPDIR/releases"
  FAKE_PYTHON="$BATS_TEST_TMPDIR/python3.14"
  UV_ARGS_FILE="$BATS_TEST_TMPDIR/uv-args"
  AGENT_HARNESS_ARGS_FILE="$BATS_TEST_TMPDIR/agent-harness-args"
  mkdir -p "$HOME_DIR" "$RELEASES"
  write_stub "$FAKE_PYTHON" '#!/bin/sh' 'exit 0'
  write_stub "$RELEASES/shfmt" '#!/bin/sh' 'exit 0'
  write_stub "$RELEASES/jq" '#!/bin/sh' "exec '$(command -v jq)' \"\$@\""
  create_agent_harness_archive
  create_ripgrep_archive
  create_uv_installer
}

function install_server() {
  env -u XDG_CONFIG_HOME -u XDG_STATE_HOME -u XDG_CACHE_HOME -u BIN_DIR \
    HOME="$HOME_DIR" \
    INSTALL_SERVER_MACHINE=x86_64 \
    AGENT_HARNESS_URL="file://$RELEASES/agent-harness.tar.xz" \
    SHFMT_URL="file://$RELEASES/shfmt" \
    RIPGREP_URL="file://$RELEASES/ripgrep.tar.gz" \
    JQ_URL="file://$RELEASES/jq" \
    UV_INSTALLER_URL="file://$RELEASES/uv_install.sh" \
    FAKE_PYTHON="$FAKE_PYTHON" \
    UV_ARGS_FILE="$UV_ARGS_FILE" \
    AGENT_HARNESS_ARGS_FILE="$AGENT_HARNESS_ARGS_FILE" \
    "$@" \
    /bin/bash "$SCRIPT"
}

function write_stub() {
  local _path="$1"
  shift
  printf '%s\n' "$@" >|"$_path"
  chmod 0755 "$_path"
}

function create_agent_harness_archive() {
  local _name="agent-harness-x86_64-unknown-linux-musl"
  mkdir -p "$BATS_TEST_TMPDIR/$_name"
  write_fake_agent_harness "$BATS_TEST_TMPDIR/$_name/agent-harness"
  tar -cJf "$RELEASES/agent-harness.tar.xz" -C "$BATS_TEST_TMPDIR" "$_name"
}

function create_ripgrep_archive() {
  local _name="ripgrep-14.1.1-x86_64-unknown-linux-musl"
  mkdir -p "$BATS_TEST_TMPDIR/$_name"
  write_stub "$BATS_TEST_TMPDIR/$_name/rg" '#!/bin/sh' 'exit 0'
  tar -czf "$RELEASES/ripgrep.tar.gz" -C "$BATS_TEST_TMPDIR" "$_name"
}

function create_uv_installer() {
  write_fake_uv "$RELEASES/uv"
  write_stub "$RELEASES/uv_install.sh" \
    '#!/bin/sh' \
    'set -eu' \
    'mkdir -p "${UV_UNMANAGED_INSTALL:?}"' \
    "cp '$RELEASES/uv' \"\$UV_UNMANAGED_INSTALL/uv\""
}

function write_fake_uv() {
  /bin/cat >|"$1" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"${UV_ARGS_FILE:?}"
case "${1:-} ${2:-}" in
  "python install") ;;
  "python find") printf '%s\n' "${FAKE_PYTHON:?}" ;;
  *) exit 2 ;;
esac
EOF
  chmod 0755 "$1"
}

# Mimics the agent-harness CLI surface the script relies on: `install` renders
# hook entry points with the source shebang, `sync-claude-settings` lets
# generated top-level keys win, and `verify` reports FAKE_VERIFY_STATUS.
function write_fake_agent_harness() {
  /bin/cat >|"$1" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"${AGENT_HARNESS_ARGS_FILE:?}"

option_value() {
  local _flag="$1"
  shift
  while [[ "$#" -gt 1 ]]; do
    if [[ "$1" == "$_flag" ]]; then
      printf '%s\n' "$2"
      return 0
    fi
    shift
  done
  return 1
}

render() {
  local _prefix="$1" _entry
  mkdir -p "$_prefix/.claude/hooks/lib" "$_prefix/.claude/statusline" "$_prefix/.codex/hooks"
  for _entry in .claude/hooks/guard_command.py .claude/statusline/statusline.py .codex/hooks/hook_translation.py; do
    printf '%s\n' '#!/usr/bin/env -S python3 -IB' 'print("hook")' >|"$_prefix/$_entry"
    chmod 0755 "$_prefix/$_entry"
  done
  printf '%s\n' '"""Shared policy."""' >|"$_prefix/.claude/hooks/lib/policy.py"
  printf '%s\n' \
    '{"model":"fable","sandbox":{"enabled":true,"network":{"allowedDomains":["api.day.app"]}}}' \
    >|"$_prefix/.claude/settings.json"
}

case "${1:-}" in
  install)
    render "$(option_value --prefix "$@")"
    ;;
  sync-claude-settings)
    source_file="$(option_value --source "$@")"
    target_file="$(option_value --target "$@")"
    merged="$(jq -s '.[1] + .[0]' "$source_file" "$target_file")"
    printf '%s\n' "$merged" >|"$target_file"
    ;;
  verify)
    exit "${FAKE_VERIFY_STATUS:-0}"
    ;;
  *)
    exit 2
    ;;
esac
EOF
  chmod 0755 "$1"
}
