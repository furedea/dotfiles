#!/usr/bin/env bats
# Validate generated Claude settings used for command_policy migration.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  SETTINGS="$REPO_ROOT/claude/settings.base.json"
}

generated_settings() {
  nix eval --json "$REPO_ROOT#lib.generatedSettings"
}

@test "generated settings are valid JSON" {
  generated_settings | jq empty
}

@test "generated settings preserve non-permission top-level settings" {
  generated="$(generated_settings)"

  [ "$(jq -r '.model' <<<"$generated")" = "$(jq -r '.model' "$SETTINGS")" ]
  [ "$(jq -r '.language' <<<"$generated")" = "$(jq -r '.language' "$SETTINGS")" ]
  [ "$(jq -r '.hooks.PreToolUse | length' <<<"$generated")" = "$(jq -r '.hooks.PreToolUse | length' "$SETTINGS")" ]
}

@test "generated settings preserve non-Bash permissions" {
  generated="$(generated_settings)"

  # The harness in nix/agents/claude_settings.nix synthesizes Edit/Write deny
  # entries for every file under agents/hooks/ plus settings.json/AGENTS.md,
  # both as $HOME/.claude/ paths and as **/dotfiles/ globs covering the
  # checkout. That layer is verified separately; this test only checks that
  # source-authored non-Bash permissions survive the generation pass.
  filter='.permissions.allow[], .permissions.deny[]
    | select(startswith("Bash(") | not)
    | select(test("^(Edit|Write)\\(\\$HOME/\\.claude/") | not)
    | select(test("^(Edit|Write)\\(\\*\\*/[^/]+/agents/") | not)'

  expected="$(jq -r "$filter" "$SETTINGS" | sort)"
  actual="$(jq -r "$filter" <<<"$generated" | sort)"

  [ "$actual" = "$expected" ]
}

@test "generated settings derive Bash allow and deny from command policy" {
  generated="$(generated_settings)"

  jq -e '.permissions.allow[] | select(. == "Bash(uv run:*)")' <<<"$generated" >/dev/null
  jq -e '.permissions.deny[] | select(. == "Bash(rm:*)")' <<<"$generated" >/dev/null
  jq -e '.permissions.deny[] | select(. == "Bash(brew install:*)")' <<<"$generated" >/dev/null
}

@test "generated settings lock every file under agents/hooks/" {
  generated="$(generated_settings)"
  dotfiles_name="$(basename "$REPO_ROOT")"

  expected_home_paths="$(
    {
      cd "$REPO_ROOT/agents/hooks" && find . -type f -print |
        sed 's|^\./|$HOME/.claude/hooks/|'
      printf '%s\n' '$HOME/.claude/CLAUDE.md' '$HOME/.claude/settings.json'
    } | sort -u
  )"
  expected_dotfiles_globs="$(
    {
      cd "$REPO_ROOT/agents/hooks" && find . -type f -print |
        sed "s|^\./|**/${dotfiles_name}/agents/hooks/|"
      printf '%s\n' "**/${dotfiles_name}/agents/AGENTS.md"
    } | sort -u
  )"
  expected_permission_paths="$(printf '%s\n%s\n' "$expected_home_paths" "$expected_dotfiles_globs" | sort -u)"

  edit_paths="$(
    jq -r '.permissions.deny[] | select(test("^Edit\\((\\$HOME/\\.claude/|\\*\\*/[^/]+/agents/)")) | capture("^Edit\\((?<p>.*)\\)$").p' <<<"$generated" |
      sort
  )"
  write_paths="$(
    jq -r '.permissions.deny[] | select(test("^Write\\((\\$HOME/\\.claude/|\\*\\*/[^/]+/agents/)")) | capture("^Write\\((?<p>.*)\\)$").p' <<<"$generated" |
      sort
  )"
  sandbox_paths="$(
    jq -r '.sandbox.filesystem.denyWrite[]' <<<"$generated" | sort
  )"

  [ "$edit_paths" = "$expected_permission_paths" ]
  [ "$write_paths" = "$expected_permission_paths" ]
  [ "$sandbox_paths" = "$expected_home_paths" ]
}

@test "generated settings exclude agents/skills/ from auto-lock" {
  generated="$(generated_settings)"

  ! jq -e '.permissions.deny[] | select(test("\\$HOME/\\.claude/skills/"))' <<<"$generated" >/dev/null
  ! jq -e '.sandbox.filesystem.denyWrite[] | select(test("\\$HOME/\\.claude/skills/"))' <<<"$generated" >/dev/null
}

@test "generated settings keep hook commands resolvable" {
  generated="$(generated_settings)"
  missing=()

  while IFS= read -r cmd; do
    resolved="${cmd/\$HOME\/.claude\//$REPO_ROOT/agents/}"
    script="$(echo "$resolved" | awk '{print $1}')"

    if [ ! -f "$script" ]; then
      resolved="${cmd/\$HOME\/.claude\//$REPO_ROOT/claude/}"
      script="$(echo "$resolved" | awk '{print $1}')"
    fi

    if [ ! -f "$script" ]; then
      missing+=("$cmd -> $script")
    fi
  done < <(jq -r '.. | objects | select(.command?) | .command' <<<"$generated")

  if [ ${#missing[@]} -gt 0 ]; then
    printf 'Missing script:\n' >&2
    printf '  %s\n' "${missing[@]}" >&2
    return 1
  fi
}
