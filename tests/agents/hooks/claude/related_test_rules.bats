#!/usr/bin/env bats
# Validates related-test rule files. The global default rules describe
# default source-to-test conventions; project extension rules add fan-out
# mappings for this repository.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../../.." && pwd)"
  RULES="$REPO_ROOT/.agents/hooks/rules/related_test_extensions.json"
  LANGUAGE_RULES="$REPO_ROOT/agents/hooks/rules/related_test_defaults.json"
  HOOKS="$REPO_ROOT/agents/hooks.json"
}

@test "project extension rules file is valid JSON" {
  jq empty "$RULES"
}

@test "default rules file is valid JSON" {
  jq empty "$LANGUAGE_RULES"
}

@test "default rules define repository test conventions" {
  jq -e '
    .bats.source_extensions == [".sh", ".bats"]
      and (.bats.test_patterns | index("{stem}.bats"))
      and (.bats.test_patterns | index("test_{stem}.bats"))
      and .python.source_extensions == [".py"]
      and (.python.test_patterns | index("test_{stem}.py"))
      and (.python.test_patterns | index("{stem}_test.py"))
      and (.python.project_markers | index("pyproject.toml"))
      and .rust.source_extensions == [".rs"]
      and (.rust.project_markers | index("Cargo.toml"))
      and .rust.integration_test_dir == "tests"
      and (.rust.source_dirs | index("src"))
      and .javascript_typescript.source_extensions == [".js", ".jsx", ".ts", ".tsx"]
      and (.javascript_typescript.test_patterns | index("{stem}.test.ts"))
      and (keys | sort) == ["bats", "javascript_typescript", "python", "rust"]
  ' "$LANGUAGE_RULES" >/dev/null
}

@test "default rules only cover test-selection families" {
  jq -e '
    [.[].lint_hook] | sort == [
      "lint_format_js.sh",
      "lint_format_py.sh",
      "lint_format_rs.sh",
      "lint_format_sh.sh"
    ]
  ' "$LANGUAGE_RULES" >/dev/null
}

@test "Codex runs related tests before stopping" {
  jq -e '
    .codex.hooks.Stop
      | any(.[]; any(.hooks[]; .command == "$HOME/.claude/hooks/run_related_tests.sh"))
  ' "$HOOKS" >/dev/null
}

@test "every project extension value is a non-empty array of strings" {
  jq -e 'to_entries | all(.value | type == "array" and length > 0 and all(. | type == "string"))' "$RULES" >/dev/null
}

@test "every project extension test file exists" {
  cd "$REPO_ROOT"
  missing=()
  while IFS= read -r t; do
    [ -f "$t" ] || missing+=("$t")
  done < <(jq -r 'values[] | .[]' "$RULES" | sort -u)
  if [ "${#missing[@]}" -gt 0 ]; then
    printf 'missing test files referenced by rules:\n' >&2
    printf '  %s\n' "${missing[@]}" >&2
    return 1
  fi
}

@test "library files fan out to their consumers" {
  audit=$(jq -r '."agents/hooks/lib/audit_log.sh"[]' "$RULES")
  [[ "$audit" == *guard_allowed_commands.bats* ]]
  [[ "$audit" == *guard_dangerous_git.bats* ]]

  parse=$(jq -r '."agents/hooks/lib/shell_parse.sh"[]' "$RULES")
  [[ "$parse" == *guard_allowed_commands.bats* ]]
  [[ "$parse" == *adapt_shell_command.bats* ]]

  lint=$(jq -r '."agents/hooks/lib/lint_format.sh"[]' "$RULES")
  [[ "$lint" == *lint_format_py.bats* ]]
  [[ "$lint" == *adapt_lint_format.bats* ]]
}

@test "glob pattern keys cover lint_format hooks" {
  result=$(jq -r '."agents/hooks/lint_format_*.sh"[]' "$RULES")
  [[ "$result" == *lint_format_hooks.bats* ]]
}

@test "secret-content patterns trigger both Claude and Codex tests" {
  result=$(jq -r '."agents/hooks/guard_secret_content.sh"[]' "$RULES")
  [[ "$result" == *guard_secret_content.bats* ]]
  [[ "$result" == *adapt_guard_secret_content.bats* ]]
}

@test "secret commit policy triggers its runtime and policy tests" {
  result=$(jq -r '."agents/hooks/rules/secret_commit_policy.json"[]' "$RULES")
  [[ "$result" == *guard_secret_commit.bats* ]]
  [[ "$result" == *secret_commit_policy.bats* ]]
}

@test "secret path policy triggers Codex hook tests" {
  result=$(jq -r '."agents/hooks/rules/secret_path_policy.json"[]' "$RULES")
  [[ "$result" == *adapt_guard_secret_paths.bats* ]]
}

@test "provider settings trigger their policy tests" {
  result=$(jq -r '."agents/claude/settings.base.json"[]' "$RULES")
  [[ "$result" == *guard_allowed_commands.bats* ]]
  [[ "$result" == *notifications.bats* ]]

  result=$(jq -r '."agents/codex/config.toml"[]' "$RULES")
  [[ "$result" == *notifications.bats* ]]

  result=$(jq -r '."agents/hooks.json"[]' "$RULES")
  [[ "$result" == *notifications.bats* ]]
  [[ "$result" == *related_test_rules.bats* ]]
}

@test "command permissions data triggers runtime tests on both providers" {
  result=$(jq -r '."agents/command_permissions.json"[]' "$RULES")
  [[ "$result" == *tests/agents/codex/execpolicy.bats* ]]
  [[ "$result" == *command_permissions_sync.bats* ]]
  [[ "$result" == *guard_allowed_commands.bats* ]]
  [[ "$result" == *guard_forbidden_commands.bats* ]]
}

@test "precise command rules trigger their runtime guards" {
  allowed=$(jq -r '."agents/hooks/rules/allowed_commands.json"[]' "$RULES")
  [[ "$allowed" == *command_permissions_sync.bats* ]]
  [[ "$allowed" == *guard_allowed_commands.bats* ]]

  forbidden=$(jq -r '."agents/hooks/rules/forbidden_commands.json"[]' "$RULES")
  [[ "$forbidden" == *guard_forbidden_commands.bats* ]]
}

@test "skill sources trigger their Python tests" {
  commit=$(jq -r '."agents/skills/git-commit-split/*"[]' "$RULES")
  [[ "$commit" == *test_branch_name.py* ]]
  [[ "$commit" == *test_build_partial_patch.py* ]]

  auditor=$(jq -r '."agents/skills/skill-auditor/*"[]' "$RULES")
  [[ "$auditor" == *test_collect_skills.py* ]]
  [[ "$auditor" == *test_generate_report.py* ]]
}
