# esa helpers open posts in Neovim, save them as WIP, and explicitly ship them.
_ESA_LAST_POST_NUMBER=""

function _esa_cleanup() {
  local _temp_dir="$1"
  command rm -f "$_temp_dir/post.md"
  command rmdir "$_temp_dir"
}

function _esa_edit() {
  local _post_number="$1"
  local _editor="${EDITOR:-nvim}"
  local _temp_dir
  _temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/esa-edit.XXXXXX") || return 1
  local _temp_file="$_temp_dir/post.md"

  local _post_json
  if ! _post_json=$(esa post view "$_post_number" --json body_md); then
    _esa_cleanup "$_temp_dir"
    return 1
  fi
  if ! print -r -- "$_post_json" | jq -er '.body_md' >|"$_temp_file"; then
    _esa_cleanup "$_temp_dir"
    return 1
  fi

  echo "editor: $_editor"
  ESA_EDIT_POST_NUMBER="$_post_number" \
    ESA_EDIT_FILE="$_temp_file" \
    "$_editor" "$_temp_file"
  local _status=$?

  if ((_status == 0)); then
    _ESA_LAST_POST_NUMBER="$_post_number"
  fi

  _esa_cleanup "$_temp_dir"
  return "$_status"
}

function _esa_find_post_number() {
  local _post="$1"
  local _query
  _query=$(jq -nr --arg post "$_post" '"full_name:" + ($post | @json)') || return 1
  local _result
  _result=$(esa post search "$_query" \
    --per-page 100 \
    --json number,name,category,full_name) || return 1
  print -r -- "$_result" | jq -er --arg post "$_post" \
    '[.posts[] | select((.category + "/" + .name) == $post)]
      | if length == 1 then .[0].number else error("post not found") end'
}

function _esa_select_post() {
  local _result
  _result=$(esa post search 'in:"Members/k-shigyo" sort:updated-desc' \
    --per-page 100 \
    --json number,full_name) || return 1
  print -r -- "$_result" \
    | jq -r '.posts[] | [.number, .full_name] | @tsv' \
    | fzf --delimiter=$'\t' --with-nth=2.. --prompt="esa > "
}

function en() {
  [[ -z "${1:-}" ]] && echo "usage: en <title>" && return 1
  local _post="Members/k-shigyo/$1"
  local _post_json
  _post_json=$(esa post create "$_post" \
    --wip \
    --message "[skip notice]" \
    --json number) || return 1
  local _post_number
  _post_number=$(print -r -- "$_post_json" | jq -er '.number') || return 1
  _esa_edit "$_post_number"
}

function ee() {
  if [[ -n "${1:-}" ]]; then
    local _post="Members/k-shigyo/$1"
    local _post_number
    _post_number=$(_esa_find_post_number "$_post") || return 1
    _esa_edit "$_post_number"
    return
  fi

  local _selection
  _selection=$(_esa_select_post) || return 1
  [[ -z "$_selection" ]] && return
  local _post_number="${_selection%%$'\t'*}"
  _esa_edit "$_post_number"
}

function eep() {
  local _post="議事録/2026年度配属/shigyo"
  local _post_number
  _post_number=$(_esa_find_post_number "$_post") || return 1
  _esa_edit "$_post_number"
}

function es() {
  local -a _message_args=()

  case "${1:-}" in
    "") ;;
    -q | --quiet | --no-notice)
      _message_args=(--message "[skip notice]")
      shift
      ;;
    *)
      echo "usage: es [-q|--quiet]"
      return 1
      ;;
  esac

  [[ -n "${1:-}" ]] && echo "usage: es [-q|--quiet]" && return 1
  [[ -z "$_ESA_LAST_POST_NUMBER" ]] \
    && echo "es: no post to ship (edit something first)" \
    && return 1
  esa post update "$_ESA_LAST_POST_NUMBER" --ship "${_message_args[@]}" \
    && _ESA_LAST_POST_NUMBER=""
}
