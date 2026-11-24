# Preserve inherited tool precedence and keep each entry only once.
typeset -U path PATH
function _insert_fallback_paths() {
  local -a _missing
  local _entry _index=1
  for _entry in "$@"; do
    (( ${path[(Ie)$_entry]} )) || _missing+=("$_entry")
  done
  (( ${#_missing} )) || return 0
  for _entry in "${path[@]}"; do
    case "$_entry" in
      /usr/local/bin|/usr/bin|/bin|/usr/sbin|/sbin) break ;;
    esac
    (( _index++ ))
  done
  path=("${(@)path[1,_index-1]}" "${_missing[@]}" "${(@)path[_index,-1]}")
}

_insert_fallback_paths "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/.gem/bin"
# Enforced on every zsh start so stale inherited environments
# (e.g. a long-running herdr server snapshot) cannot override it.
export EDITOR=nvim
export VISUAL=nvim
# agent-browser bundles no browser on Darwin; use the Homebrew cask Chrome.
export AGENT_BROWSER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# T3 Code sends telemetry unless this parses as false; the desktop app forwards it to its server (ADR-0048).
export T3CODE_TELEMETRY_ENABLED=false
# Belt and braces: relay tracing also stops when T3 OTel export is disabled (ADR-0048).
export T3CODE_OTEL_SDK_DISABLED=true
