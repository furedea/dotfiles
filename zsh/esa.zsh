# esa helpers save marked Neovim buffers as WIP; `es` explicitly ships the last post.
_ESA_LAST_POST=""

function _esa_edit() {
  local _post="$1"
  local _editor="${EDITOR:-nvim}"
  local _post_number
  _post_number=$(kasa info "$_post" | jq -er '.number') || return 1
  local _temp_dir
  _temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/esa-edit.XXXXXX") || return 1
  local _temp_file="$_temp_dir/post.md"

  if ! kasa cat "$_post" >"$_temp_file"; then
    command rm -f "$_temp_file"
    command rmdir "$_temp_dir"
    return 1
  fi

  echo "editor: $_editor"
  ESA_EDIT_POST="$_post" \
    ESA_EDIT_POST_NUMBER="$_post_number" \
    ESA_EDIT_FILE="$_temp_file" \
    "$_editor" "$_temp_file"
  local _status=$?

  if ((_status == 0)); then
    _ESA_LAST_POST="$_post"
  fi

  command rm -f "$_temp_file"
  command rmdir "$_temp_dir"
  return "$_status"
}

function en() {
  [[ -z "$1" ]] && echo "usage: en <title>" && return 1
  local _url
  _url=$(kasa touch --no-notice "Members/k-shigyo/$1") || return 1
  _esa_edit "$_url"
}

function ee() {
  local _post
  if [[ -n "$1" ]]; then
    _post="Members/k-shigyo/$1"
  else
    _post=$(kasa ls "Members/k-shigyo/" | awk '{print $NF}' | fzf --prompt="esa > ")
    [[ -z "$_post" ]] && return
  fi
  _esa_edit "$_post"
}

function eep() {
  _esa_edit "議事録/2026年度配属/shigyo"
}

function es() {
  local _notice_flag="--notice"

  case "$1" in
    "") ;;
    -q | --quiet | --no-notice)
      _notice_flag="--no-notice"
      shift
      ;;
    *)
      echo "usage: es [-q|--quiet]"
      return 1
      ;;
  esac

  [[ -n "$1" ]] && echo "usage: es [-q|--quiet]" && return 1
  [[ -z "$_ESA_LAST_POST" ]] && echo "es: no post to ship (edit something first)" && return 1
  kasa unwip -f "$_notice_flag" "$_ESA_LAST_POST" && _ESA_LAST_POST=""
}
