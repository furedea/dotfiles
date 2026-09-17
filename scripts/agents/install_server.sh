#!/usr/bin/env bash
set -euCo pipefail

function usage() {
  cat <<EOF >&2
Description:
    Deploy the agents/ harness on a Linux server without Nix. Installs pinned
    user-space release binaries and a uv-managed Python under the home
    directory, renders the harness with agent-harness, pins hook shebangs to
    that interpreter, and writes a shell snippet for the login shell.

Usage:
    $0

Options:
    --help, -h: print this

Host-specific locations, from the environment or
\$XDG_CONFIG_HOME/dotfiles/install_server.env:
    BIN_DIR                user-space binaries (default: ~/.local/bin)
    BATS_PREFIX            bats-core installation (default: ~/.local/share/bats-core)
    PYTHON_VERSION         uv-managed interpreter (default: 3.14)
    UV_PYTHON_INSTALL_DIR  interpreter location (uv default: ~/.local/share/uv/python)
    UV_CACHE_DIR           uv cache (uv default: ~/.cache/uv)
    XDG_STATE_HOME         hook state and logs (default: ~/.local/state)
    XDG_CACHE_HOME         hook cache (default: ~/.cache)
EOF
  exit 1
}

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
readonly REPO_ROOT
readonly HARNESS_PREFIX="${HOME:?}"
readonly CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles"
readonly HOST_ENV_FILE="${INSTALL_SERVER_ENV:-$CONFIG_DIR/install_server.env}"
readonly CLAUDE_SETTINGS_OVERRIDE="${CLAUDE_SETTINGS_OVERRIDE:-$CONFIG_DIR/claude_settings_override.json}"
readonly ENV_SNIPPET="$CONFIG_DIR/agent_env.sh"
readonly SOURCE_SHEBANG="#!/usr/bin/env -S python3"

function load_host_env() {
  [[ -f "$HOST_ENV_FILE" ]] || return 0
  set -a
  # shellcheck source=/dev/null
  source "$HOST_ENV_FILE"
  set +a
}
load_host_env

readonly BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
readonly PYTHON_VERSION="${PYTHON_VERSION:-3.14}"
MACHINE="${INSTALL_SERVER_MACHINE:-$(uname -m)}"
readonly MACHINE
readonly AGENT_HARNESS_VERSION="${AGENT_HARNESS_VERSION:-latest}"
readonly SHFMT_VERSION="${SHFMT_VERSION:-3.13.1}"
readonly RIPGREP_VERSION="${RIPGREP_VERSION:-14.1.1}"
readonly JQ_VERSION="${JQ_VERSION:-1.8.1}"
readonly BATS_VERSION="${BATS_VERSION:-1.13.0}"
readonly BATS_PREFIX="${BATS_PREFIX:-${XDG_DATA_HOME:-$HOME/.local/share}/bats-core}"
readonly UV_INSTALLER_URL="${UV_INSTALLER_URL:-https://astral.sh/uv/install.sh}"
readonly SHFMT_URL="${SHFMT_URL:-https://github.com/mvdan/sh/releases/download/v${SHFMT_VERSION}/shfmt_v${SHFMT_VERSION}_linux_amd64}"
readonly RIPGREP_URL="${RIPGREP_URL:-https://github.com/BurntSushi/ripgrep/releases/download/${RIPGREP_VERSION}/ripgrep-${RIPGREP_VERSION}-x86_64-unknown-linux-musl.tar.gz}"
readonly JQ_URL="${JQ_URL:-https://github.com/jqlang/jq/releases/download/jq-${JQ_VERSION}/jq-linux-amd64}"
readonly BATS_URL="${BATS_URL:-https://github.com/bats-core/bats-core/archive/refs/tags/v${BATS_VERSION}.tar.gz}"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/install_server.XXXXXX")"
readonly WORK_DIR
trap 'rm -rf "$WORK_DIR"' EXIT

function main() {
  [[ "$#" -eq 0 ]] || usage
  require_release_binaries
  mkdir -p "$BIN_DIR" "$CONFIG_DIR"
  install_tool agent-harness "${AGENT_HARNESS_URL:-$(agent_harness_release_url)}" agent-harness
  install_tool shfmt "$SHFMT_URL"
  install_tool rg "$RIPGREP_URL" rg
  install_tool jq "$JQ_URL"
  install_bats
  install_uv
  local _python
  _python="$(install_python)"
  render_harness
  pin_python_shebangs "$_python"
  apply_claude_settings_override
  write_env_snippet
  verify_harness
}

function require_release_binaries() {
  [[ "$MACHINE" == x86_64 ]] && return 0
  cat <<EOF >&2
Release binaries are published only for x86_64 Linux; this machine is $MACHINE.
Build agent-harness from source instead:
    cargo install --locked --git https://github.com/furedea/agent-harness agent-harness
EOF
  exit 1
}

function agent_harness_release_url() {
  local _releases="https://github.com/furedea/agent-harness/releases"
  local _asset="agent-harness-x86_64-unknown-linux-musl.tar.xz"
  if [[ "$AGENT_HARNESS_VERSION" == latest ]]; then
    printf '%s/latest/download/%s\n' "$_releases" "$_asset"
  else
    printf '%s/download/v%s/%s\n' "$_releases" "$AGENT_HARNESS_VERSION" "$_asset"
  fi
}

# Installs a release binary, or the named member of a release archive, into BIN_DIR.
function install_tool() {
  local _name="$1" _url="$2" _member="${3:-}"
  if [[ -x "$BIN_DIR/$_name" ]]; then
    printf 'keep %s\n' "$BIN_DIR/$_name"
    return 0
  fi
  local _download="$WORK_DIR/$_name.download"
  download "$_url" "$_download"
  if [[ -n "$_member" ]]; then
    _download="$(extract_member "$_download" "$_member")"
  fi
  install -m 0755 "$_download" "$BIN_DIR/$_name"
  printf 'install %s\n' "$BIN_DIR/$_name"
}

function download() {
  local _url="$1" _destination="$2"
  curl --retry 3 --retry-delay 2 -fsSL "$_url" -o "$_destination"
}

function extract_member() {
  local _archive="$1" _member="$2"
  printf '%s/%s\n' "$(extract_archive "$_archive")" "$_member"
}

function extract_archive() {
  local _archive="$1" _directory
  _directory="$(mktemp -d "$WORK_DIR/extract.XXXXXX")"
  tar -xf "$_archive" -C "$_directory" --strip-components=1
  printf '%s\n' "$_directory"
}

# bats-core is plain Bash; its installer lays out bin/ and libexec/ under one prefix.
function install_bats() {
  if [[ -x "$BIN_DIR/bats" ]]; then
    printf 'keep %s\n' "$BIN_DIR/bats"
    return 0
  fi
  local _download="$WORK_DIR/bats.download" _source
  download "$BATS_URL" "$_download"
  _source="$(extract_archive "$_download")"
  bash "$_source/install.sh" "$BATS_PREFIX" >/dev/null
  ln -sf "$BATS_PREFIX/bin/bats" "$BIN_DIR/bats"
  printf 'install %s\n' "$BIN_DIR/bats"
}

function install_uv() {
  if [[ -x "$BIN_DIR/uv" ]]; then
    printf 'keep %s\n' "$BIN_DIR/uv"
    return 0
  fi
  download "$UV_INSTALLER_URL" "$WORK_DIR/uv_install.sh"
  UV_UNMANAGED_INSTALL="$BIN_DIR" sh "$WORK_DIR/uv_install.sh"
  printf 'install %s\n' "$BIN_DIR/uv"
}

# Prints the absolute path of the managed interpreter.
function install_python() {
  "$BIN_DIR/uv" python install "$PYTHON_VERSION" >&2
  "$BIN_DIR/uv" python find --managed-python "$PYTHON_VERSION"
}

# Claude Code edits its settings at runtime: generated keys win, other keys survive.
function render_harness() {
  local _settings="$HARNESS_PREFIX/.claude/settings.json"
  local _previous="$WORK_DIR/previous_settings.json"
  if [[ -f "$_settings" ]]; then
    cp "$_settings" "$_previous"
  fi
  "$BIN_DIR/agent-harness" install --source "$REPO_ROOT/agents" --prefix "$HARNESS_PREFIX"
  [[ -f "$_previous" ]] || return 0
  "$BIN_DIR/agent-harness" sync-claude-settings --source "$_settings" --target "$_previous"
  install -m 0600 "$_previous" "$_settings"
}

# Mirrors Nix's patchShebangs so hooks never depend on which python3 PATH resolves.
function pin_python_shebangs() {
  local _python="$1" _directory _file
  for _directory in "$HARNESS_PREFIX/.claude/hooks" "$HARNESS_PREFIX/.claude/statusline" "$HARNESS_PREFIX/.codex/hooks"; do
    [[ -d "$_directory" ]] || continue
    while IFS= read -r -d '' _file; do
      pin_python_shebang "$_python" "$_file"
    done < <(find "$_directory" -type f -name '*.py' -print0)
  done
}

function pin_python_shebang() {
  local _python="$1" _file="$2" _first_line
  _first_line="$(head -n 1 "$_file")"
  [[ "$_first_line" == "$SOURCE_SHEBANG"* ]] || return 0
  local _pinned="$WORK_DIR/pinned.py"
  {
    printf '#!%s%s\n' "$_python" "${_first_line#"$SOURCE_SHEBANG"}"
    tail -n +2 "$_file"
  } >|"$_pinned"
  install -m 0755 "$_pinned" "$_file"
}

function apply_claude_settings_override() {
  [[ -f "$CLAUDE_SETTINGS_OVERRIDE" ]] || return 0
  local _settings="$HARNESS_PREFIX/.claude/settings.json"
  local _merged="$WORK_DIR/settings.json"
  "$BIN_DIR/jq" -s '.[0] * .[1]' "$_settings" "$CLAUDE_SETTINGS_OVERRIDE" >|"$_merged"
  install -m 0600 "$_merged" "$_settings"
  printf 'override %s\n' "$_settings"
}

# Hooks run inside the agent's environment, so the login shell must export the same locations.
function write_env_snippet() {
  {
    printf '%s\n' \
      '# Generated by scripts/agents/install_server.sh; source this file from the login shell.' \
      "case \":\$PATH:\" in" \
      "  *\":$BIN_DIR:\"*) ;;" \
      "  *) export PATH=\"$BIN_DIR:\$PATH\" ;;" \
      'esac'
    write_env_exports XDG_CONFIG_HOME XDG_STATE_HOME XDG_CACHE_HOME
  } >|"$ENV_SNIPPET"
  printf 'Add this line to the login shell profile (~/.profile or ~/.bashrc):\n    . "%s"\n' "$ENV_SNIPPET"
}

function write_env_exports() {
  local _name
  for _name in "$@"; do
    if [[ -n "${!_name:-}" ]]; then
      printf 'export %s="%s"\n' "$_name" "${!_name}"
    fi
  done
}

function verify_harness() {
  PATH="$BIN_DIR:$PATH" "$BIN_DIR/agent-harness" verify --source "$REPO_ROOT/agents" --prefix "$HARNESS_PREFIX"
}

main "$@"
