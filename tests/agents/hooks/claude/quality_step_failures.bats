#!/usr/bin/env bats
# Every formatter must preserve execution errors for the agent.

setup() {
  load test-helper/setup
  mkdir -p "$BATS_TEST_TMPDIR/bin"
  export PATH="$BATS_TEST_TMPDIR/bin:$PATH"
  local _tool
  for _tool in shfmt shellcheck oxfmt oxlint nixfmt statix deadnix stylua selene tex-fmt chktex autocorrect prettierd dprint actionlint; do
    # shellcheck disable=SC2016 # Expanded by the stub, not by fixture creation.
    printf '#!/usr/bin/env bash\nif [[ "${0##*/}" == "$FAILED_TOOL" ]]; then echo "formatter unavailable at runtime" >&2; exit 2; fi\n' >"$BATS_TEST_TMPDIR/bin/$_tool"
    chmod +x "$BATS_TEST_TMPDIR/bin/$_tool"
  done
}

@test "format hooks preserve errors across supported file types" {
  local _case _hook _extension _tool _context
  for _case in 'sh sh shfmt' 'js js oxfmt' 'nix nix nixfmt' 'lua lua stylua' 'tex bib tex-fmt' 'txt txt autocorrect' 'md md prettierd' 'json_toml json dprint'; do
    read -r _hook _extension _tool <<<"$_case"
    export FAILED_TOOL="$_tool"
    touch "$BATS_TEST_TMPDIR/source.$_extension"

    run bash "$HOOK_DIR/lint_format_$_hook.sh" <<<"$(make_post_tool_input "$BATS_TEST_TMPDIR/source.$_extension")"

    [ "$status" -eq 0 ]
    _context=$(jq -r '.hookSpecificOutput.additionalContext' <<<"$output")
    if [[ "$_context" != *"Quality check failed"* || "$_context" != *"$_tool format · $BATS_TEST_TMPDIR/source.$_extension · exit 2"* || "$_context" != *"Error: formatter unavailable at runtime"* ]]; then
      printf 'Missing failure context for %s: %s\n' "$_hook" "$output"
      return 1
    fi
  done
}

@test "lint failures use the same quality notification with target and exit status" {
  local _case _hook _extension _tool _context _file
  for _case in 'sh sh shellcheck' 'js js oxlint' 'nix nix statix' 'nix nix deadnix' 'lua lua selene' 'tex tex chktex' 'json_toml toml dprint' 'gha yml actionlint'; do
    read -r _hook _extension _tool <<<"$_case"
    export FAILED_TOOL="$_tool"
    mkdir -p "$BATS_TEST_TMPDIR/.github/workflows"
    _file="$BATS_TEST_TMPDIR/.github/workflows/source.$_extension"
    touch "$_file"
    run bash "$HOOK_DIR/lint_format_$_hook.sh" <<<"$(make_post_tool_input "$_file")"
    [ "$status" -eq 0 ]
    _context=$(jq -r '.hookSpecificOutput.additionalContext' <<<"$output")
    [[ "$_context" == *"Quality check failed"* ]]
    [[ "$_context" == *"$_tool lint · $_file · exit 2"* ]]
    [[ "$_context" == *"Error: formatter unavailable at runtime"* ]]
  done
}




@test "chktex warnings remain visible even when the command exits zero" {
  printf '#!/usr/bin/env bash\nprintf "Warning 1: unexpected spacing\\n"\n' >"$BATS_TEST_TMPDIR/bin/chktex"
  export FAILED_TOOL=""
  touch "$BATS_TEST_TMPDIR/source.tex"
  run bash "$HOOK_DIR/lint_format_tex.sh" <<<"$(make_post_tool_input "$BATS_TEST_TMPDIR/source.tex")"
  [ "$status" -eq 0 ]
  local _context
  _context=$(jq -r '.hookSpecificOutput.additionalContext' <<<"$output")
  [ "$_context" = "Quality check failed"$'\n'"chktex lint · $BATS_TEST_TMPDIR/source.tex · exit 0"$'\n'"Diagnostics: Warning 1: unexpected spacing" ]
}
