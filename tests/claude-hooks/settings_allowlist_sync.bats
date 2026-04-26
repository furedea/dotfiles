#!/usr/bin/env bats
# Tests that every Bash permission in settings.json has matching coverage
# in command_allowlist.sh.
#
# Invariant: each Bash(prefix:*) allow entry in settings.json must have
# a corresponding GOVERNED_PREFIXES entry AND at least one ALLOWED_PATTERNS
# entry in command_allowlist.sh.
#
# This prevents auto-approved commands from bypassing the allowlist hook.

setup() {
  load test_helper/setup
  SETTINGS="$REPO_ROOT/claude/settings.json"
  ALLOWLIST="$REPO_ROOT/claude/hooks/command_allowlist.sh"
}

# Read settings.json, stripping JSONC-style full-line // comments before parsing.
# Uses ^-anchored match so // inside JSON strings (e.g., URLs) is preserved.
# Removes blank lines and fixes trailing commas left behind by removed lines.
read_settings() {
  sed 's|^[[:space:]]*//.*||' "$SETTINGS" \
    | grep -v '^[[:space:]]*$' \
    | python3 -c 'import sys, re; data = sys.stdin.read(); sys.stdout.write(re.sub(r",(\s*[\]\}])", r"\1", data))' \
    | jq "$@"
}

# Extract Bash allow prefixes from settings.json.
# "Bash(gh api:*)" → "gh api"
get_settings_bash_prefixes() {
  read_settings -r '.permissions.allow[]' \
    | grep '^Bash(' \
    | sed -E 's/^Bash\(([^:]+):\*\)$/\1/'
}

# Extract GOVERNED_PREFIXES entries from command_allowlist.sh.
get_governed_prefixes() {
  sed -n '/^GOVERNED_PREFIXES=(/,/^)/p' "$ALLOWLIST" \
    | grep -E '^[[:space:]]+"' \
    | sed -E 's/^[[:space:]]+"([^"]+)"$/\1/'
}

# Extract ALLOWED_PATTERNS entries from command_allowlist.sh (just the raw patterns).
get_allowed_patterns() {
  sed -n '/^ALLOWED_PATTERNS=(/,/^)/p' "$ALLOWLIST" \
    | grep -E "^[[:space:]]+['\"]" \
    | sed -E "s/^[[:space:]]+['\"]([^'\"]*)['\"].*/\1/"
}

# ============================================================
# Core invariant tests
# ============================================================

@test "every Bash allow in settings.json has a GOVERNED_PREFIXES entry" {
  local missing=()
  local governed
  governed=$(get_governed_prefixes)

  while IFS= read -r prefix; do
    if ! echo "$governed" | grep -qxF "$prefix"; then
      missing+=("$prefix")
    fi
  done <<< "$(get_settings_bash_prefixes)"

  if [ ${#missing[@]} -gt 0 ]; then
    echo "Bash prefixes in settings.json missing from GOVERNED_PREFIXES:"
    printf '  - %s\n' "${missing[@]}"
    echo ""
    echo "Fix: add the missing prefix(es) to GOVERNED_PREFIXES in"
    echo "  .claude/hooks/command_allowlist.sh"
    return 1
  fi
}

@test "every GOVERNED_PREFIXES entry has a Bash allow in settings.json" {
  local missing=()
  local settings_prefixes
  settings_prefixes=$(get_settings_bash_prefixes)

  while IFS= read -r prefix; do
    if ! echo "$settings_prefixes" | grep -qxF "$prefix"; then
      missing+=("$prefix")
    fi
  done <<< "$(get_governed_prefixes)"

  if [ ${#missing[@]} -gt 0 ]; then
    echo "GOVERNED_PREFIXES entries missing from settings.json Bash allows:"
    printf '  - %s\n' "${missing[@]}"
    echo ""
    echo "Fix: add Bash(<prefix>:*) to permissions.allow in"
    echo "  .claude/settings.json, or remove the prefix from GOVERNED_PREFIXES"
    return 1
  fi
}

@test "every GOVERNED_PREFIXES entry has at least one ALLOWED_PATTERNS entry" {
  local missing=()
  local patterns
  patterns=$(get_allowed_patterns)

  while IFS= read -r prefix; do
    # Escape regex metacharacters in prefix for grep
    local escaped
    escaped=$(printf '%s' "$prefix" | sed 's/[.[\*^$()+?{|]/\\&/g')
    # Check if any pattern starts with ^ followed by the prefix and a delimiter
    if ! echo "$patterns" | grep -qE "^\^${escaped}( |\(|\$|\\\\s)"; then
      missing+=("$prefix")
    fi
  done <<< "$(get_governed_prefixes)"

  if [ ${#missing[@]} -gt 0 ]; then
    echo "GOVERNED_PREFIXES entries with no matching ALLOWED_PATTERNS:"
    printf '  - %s\n' "${missing[@]}"
    echo ""
    echo "Fix: add at least one allowed regex pattern for each prefix in"
    echo "  .claude/hooks/command_allowlist.sh"
    return 1
  fi
}
