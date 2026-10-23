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
