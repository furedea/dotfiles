# The parent shell owns the last edited post; Python owns CLI and editor workflows.
_ESA_LAST_POST_NUMBER=""
typeset -g _ESA_HELPER="${${(%):-%N}:A:h}/esa.py"

function _esa_run() {
  local _result_file
  _result_file=$(mktemp "${TMPDIR:-/tmp}/esa-result.XXXXXX") || return 1
  local _python="${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles/bin/python3"
  [[ -x "$_python" ]] || _python=python3
  command "$_python" -I -B "$_ESA_HELPER" "$_result_file" "$_ESA_LAST_POST_NUMBER" "$@"
  local _result=$?
  if (( _result == 0 )) && [[ -s "$_result_file" ]]; then
    IFS= read -r _ESA_LAST_POST_NUMBER < "$_result_file"
  fi
  command rm -f "$_result_file"
  return "$_result"
}

function en() { _esa_run en "$@"; }
function ee() { _esa_run ee "$@"; }
function eep() { _esa_run eep "$@"; }
function es() { _esa_run es "$@"; }
function _esa_edit() { _esa_run edit "$@"; }
