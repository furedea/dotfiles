#!/usr/bin/env bats
# Tests for codex/hooks/adapt_lint_format.sh
# Focuses on patch_paths extraction and hook_for_path dispatch logic.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/codex/hooks/adapt_lint_format.sh"
}

@test "prints usage with --help" {
  run "$HOOK" --help
  [ "$status" -ne 0 ]
  [[ "$output" == *"Usage"* ]]
}

@test "patch_paths extracts Add File paths" {
  input='*** Add File: src/main.py
some content
*** Add File: src/lib.rs'
  result=$(printf '%s' "$input" | awk '
    /^\*\*\* (Add|Update|Delete) File: / {
      sub(/^\*\*\* (Add|Update|Delete) File: /, "")
      print
    }
    /^\*\*\* Move to: / {
      sub(/^\*\*\* Move to: /, "")
      print
    }
  ' | sort -u)
  [ "$result" = "$(printf 'src/lib.rs\nsrc/main.py')" ]
}

@test "patch_paths extracts Update File paths" {
  input='*** Update File: src/app.ts
@@ -1,3 +1,4 @@
+new line'
  result=$(printf '%s' "$input" | awk '
    /^\*\*\* (Add|Update|Delete) File: / {
      sub(/^\*\*\* (Add|Update|Delete) File: /, "")
      print
    }
  ' | sort -u)
  [ "$result" = "src/app.ts" ]
}

@test "patch_paths extracts Move to paths" {
  input='*** Delete File: old.py
*** Move to: new.py'
  result=$(printf '%s' "$input" | awk '
    /^\*\*\* (Add|Update|Delete) File: / {
      sub(/^\*\*\* (Add|Update|Delete) File: /, "")
      print
    }
    /^\*\*\* Move to: / {
      sub(/^\*\*\* Move to: /, "")
      print
    }
  ' | sort -u)
  [ "$result" = "$(printf 'new.py\nold.py')" ]
}

@test "patch_paths deduplicates paths" {
  input='*** Update File: src/main.py
@@ context
*** Update File: src/main.py
@@ more context'
  result=$(printf '%s' "$input" | awk '
    /^\*\*\* (Add|Update|Delete) File: / {
      sub(/^\*\*\* (Add|Update|Delete) File: /, "")
      print
    }
  ' | sort -u)
  [ "$result" = "src/main.py" ]
}

@test "hook_for_path maps py to lint_format_py" {
  # Source the function via a subshell trick
  result=$(CLAUDE_HOOKS_DIR="/stub" bash -c '
    hook_for_path() {
      local _file_path="$1"
      case "$_file_path" in
        *.py) echo "$CLAUDE_HOOKS_DIR/lint_format_py.sh" ;;
        *.sh) echo "$CLAUDE_HOOKS_DIR/lint_format_sh.sh" ;;
        *.js|*.ts|*.jsx|*.tsx) echo "$CLAUDE_HOOKS_DIR/lint_format_js.sh" ;;
        *.nix) echo "$CLAUDE_HOOKS_DIR/lint_format_nix.sh" ;;
        *.lua) echo "$CLAUDE_HOOKS_DIR/lint_format_lua.sh" ;;
        *) return 1 ;;
      esac
    }
    hook_for_path "src/main.py"
  ')
  [ "$result" = "/stub/lint_format_py.sh" ]
}

@test "hook_for_path returns failure for unknown extension" {
  run bash -c '
    CLAUDE_HOOKS_DIR="/stub"
    hook_for_path() {
      local _file_path="$1"
      case "$_file_path" in
        *.py|*.sh|*.js|*.ts|*.jsx|*.tsx|*.rs|*.nix|*.md|*.markdown|*.json|*.toml|*.yml|*.yaml|*.txt|*.lua|*.tex|*.bib|*.cls|*.sty) echo "matched" ;;
        *) return 1 ;;
      esac
    }
    hook_for_path "README"
  '
  [ "$status" -ne 0 ]
}
