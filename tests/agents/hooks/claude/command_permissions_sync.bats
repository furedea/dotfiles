#!/usr/bin/env bats
# Tests that generated Bash permissions, shared prefixes, and precise regex rules stay aligned.

setup() {
  load test-helper/setup
  AGENT_HARNESS_BIN="${AGENT_HARNESS_BIN:-agent-harness}"
  COMMAND_PERMISSIONS="$REPO_ROOT/agents/command_permissions.json"
  ALLOWED_RULES="$REPO_ROOT/agents/hooks/rules/allowed_commands.json"
}

read_settings() {
  local settings

  settings="$BATS_TEST_TMPDIR/generated_settings.json"
  "$AGENT_HARNESS_BIN" --profile minimal generate-claude-settings \
    --source "$REPO_ROOT/agents" \
    --output "$settings"
  jq "$@" "$settings"
}

get_settings_allow_prefixes() {
  read_settings -r '.permissions.allow[]' |
    grep '^Bash(' |
    sed -E 's/^Bash\(([^:]+):\*\)$/\1/'
}

get_policy_allow_prefixes() {
  jq -r '.rules[] | select(.decision == "allow") | .prefix | join(" ")' "$COMMAND_PERMISSIONS"
}

get_policy_ask_prefixes() {
  jq -r '.rules[] | select(.decision == "ask") | .prefix | join(" ")' "$COMMAND_PERMISSIONS"
}

get_allowed_patterns() {
  jq -r '.rules[].patterns[]' "$ALLOWED_RULES"
}

assert_lines_contain() {
  local _expected="$1"
  local _actual="$2"
  local _label="$3"
  local _missing=()
  local _line

  while IFS= read -r _line; do
    if ! echo "$_actual" | grep -qxF "$_line"; then
      _missing+=("$_line")
    fi
  done <<<"$_expected"

  if [ ${#_missing[@]} -gt 0 ]; then
    echo "$_label"
    printf '  - %s\n' "${_missing[@]}"
    return 1
  fi
}

@test "generated runtime command permissions are accepted by the shell guard" {
  local _runtime_permissions="$BATS_TEST_TMPDIR/command_permissions.json"

  "$AGENT_HARNESS_BIN" --profile minimal generate-command-permissions \
    --source "$REPO_ROOT/agents" \
    --output "$_runtime_permissions"

  run env AGENT_COMMAND_PERMISSIONS="$_runtime_permissions" \
    bash "$HOOK_DIR/guard_allowed_commands.sh" <<<"$(make_input "gh pr list")"

  [ "$status" -eq 0 ]
}

@test "every generated Bash allow has a shared allow prefix" {
  assert_lines_contain \
    "$(get_settings_allow_prefixes)" \
    "$(get_policy_allow_prefixes)" \
    "Generated Bash allows missing from command_permissions.json:"
}

@test "every shared allow prefix is generated as a Bash allow" {
  assert_lines_contain \
    "$(get_policy_allow_prefixes)" \
    "$(get_settings_allow_prefixes)" \
    "Shared allow prefixes missing from generated Claude permissions:"
}

@test "every shared allow prefix has at least one global regex" {
  local missing=()
  local patterns
  local prefix
  local escaped

  patterns=$(get_allowed_patterns)
  while IFS= read -r prefix; do
    # shellcheck disable=SC2016
    escaped=$(printf '%s' "$prefix" | sed 's/[.[\*^$()+?{|]/\\&/g')
    if ! echo "$patterns" | grep -qE "^\^${escaped}( |\(|\$|\\\\s)"; then
      missing+=("$prefix")
    fi
  done <<<"$(get_policy_allow_prefixes)"

  if [ ${#missing[@]} -gt 0 ]; then
    echo "Shared allow prefixes missing from hooks/rules/allowed_commands.json:"
    printf '  - %s\n' "${missing[@]}"
    return 1
  fi
}

@test "manual verification prefixes render only as Claude ask permissions" {
  local expected
  expected=$(cat <<'EOF'
actionlint
autocorrect --lint
bats
bash -n
cargo test
cargo check
cargo clippy
cargo fmt --check
commitlint
deadnix
dprint check
nixfmt --check
npm test
npm run test
npm run lint
npm run format-check
npm run typecheck
node --test
oxfmt --check
oxlint
pnpm test
pnpm run test
pnpm run lint
pnpm run format-check
pnpm run typecheck
selene
shellcheck
shfmt -d
statix
stylua --check
tex-fmt --check
tsgolint
uv run pytest
uv run ruff
uv run ty
EOF
)

  assert_lines_contain "$expected" "$(get_policy_ask_prefixes)" \
    "Manual verification prefixes missing from shared ask rules:"

  local generated_ask
  generated_ask=$(read_settings -r '.permissions.ask[]' | sed -E 's/^Bash\(([^:]+):\*\)$/\1/')
  assert_lines_contain "$expected" "$generated_ask" \
    "Manual verification prefixes missing from generated Claude ask permissions:"

  local generated_allow
  generated_allow=$(get_settings_allow_prefixes)
  while IFS= read -r prefix; do
    ! echo "$generated_allow" | grep -qxF "$prefix"
  done <<<"$expected"
}

@test "manual verification ask prefixes have no ancestor allow prefix" {
  local ask_prefix
  local allow_prefix

  while IFS= read -r ask_prefix; do
    while IFS= read -r allow_prefix; do
      [[ "$ask_prefix" != "$allow_prefix" ]]
      [[ "$ask_prefix" != "$allow_prefix "* ]]
    done <<<"$(get_policy_allow_prefixes)"
  done <<<"$(get_policy_ask_prefixes)"
}
