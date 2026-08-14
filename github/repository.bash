# Shared GitHub repository identifier resolution.

function resolve_repository() {
  local _repository="$1"

  if [[ "$_repository" == */* ]]; then
    printf '%s\n' "$_repository"
    return
  fi

  local _owner
  _owner=$(gh api user --jq .login)
  printf '%s/%s\n' "$_owner" "$_repository"
}
