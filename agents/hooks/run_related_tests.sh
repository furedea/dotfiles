#!/usr/bin/env bash

# run_related_tests.sh
# Stop hook: differential test gate. Blocks completion when relevant verification
# fails, times out, or cannot run.
# Always exits 0 (block signal is JSON, not status).
# Changes include committed, staged, unstaged, and untracked paths since the
# merge base with the configured base branch.
#
# Test selection combines three sources:
#   1. Project-specific extension rules at
#      <repo>/.agents/hooks/rules/related_test_extensions.json
#      (optional). A JSON object whose keys are bash-glob patterns matched
#      against changed paths; values are lists of test files or Bats test
#      directories. Use this to express fan-out (library -> consumers) and
#      cross-language mappings that the basename heuristic cannot infer.
#   2. Global default rules installed beside this hook under rules/.
#      These define default source extensions, test directories, and basename
#      patterns such as .py -> test_<stem>.py.
#   3. Per-language basename heuristic driven by the global default rules.
#
# Vitest runs both explicit/basename targets and its dependency-aware related
# selection. Bats and pytest can fall back to their full suites. Rust runs
# cargo test <stem> for mapped unit filters and cargo test --test <stem> for
# matching integration test targets.

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly RESULT_MAX_LINES=50
readonly RESULT_MAX_CHARS=4000
RESULTS=""
HAS_FAILURES=0

emit_block() {
  local _results="$1"
  jq -cn --arg reason "Verification did not pass before completion."$'\n\n'"$_results" \
    '{decision:"block", reason:$reason}'
}

emit_success() {
  local _results="$1"
  jq -cn --arg message "Verification passed before completion."$'\n\n'"$_results" \
    '{systemMessage:$message}'
}

emit_skip() {
  local _reason="$1"
  local _message="Verification skipped before completion."
  _message+=$'\n\n'
  _message+="skipped: $_reason"

  jq -cn --arg message "$_message" \
    '{systemMessage:$message}'
}

append_result() {
  local _check="$1"
  local _status="$2"
  local _scope="$3"
  local _command="$4"
  local _result="$5"

  RESULTS+="$_status: $_check"
  [ -n "$_scope" ] && RESULTS+=" ($_scope)"
  RESULTS+=$'\n'
  RESULTS+="command: $_command"$'\n'
  if [ -n "$_result" ]; then
    RESULTS+="result: $(truncate_result "$_result")"$'\n'
  fi
  RESULTS+=$'\n'

  case "$_status" in
    passed | skipped) ;;
    *) HAS_FAILURES=1 ;;
  esac
}

truncate_result() {
  local _result="$1"
  local _truncated
  local _was_truncated=false

  _truncated=$(printf '%s\n' "$_result" | tail -n "$RESULT_MAX_LINES")
  [ "$_truncated" != "$_result" ] && _was_truncated=true
  if [ "${#_truncated}" -gt "$RESULT_MAX_CHARS" ]; then
    _truncated="${_truncated: -$RESULT_MAX_CHARS}"
    _was_truncated=true
  fi

  if [ "$_was_truncated" = true ]; then
    printf '[output truncated; showing at most %s lines and %s characters]\n' \
      "$RESULT_MAX_LINES" "$RESULT_MAX_CHARS"
  fi
  printf '%s\n' "$_truncated"
}

format_command() {
  local _formatted=""
  local _argument

  for _argument in "$@"; do
    printf -v _argument '%q' "$_argument"
    _formatted+="${_formatted:+ }$_argument"
  done
  printf '%s\n' "$_formatted"
}

format_command_summary() {
  local _target_count="$1"
  shift

  if [ "$_target_count" -eq 0 ]; then
    format_command "$@"
    return 0
  fi

  local _prefix_count
  _prefix_count=$(($# - _target_count))
  local -a _prefix=("${@:1:$_prefix_count}")
  printf '%s <%s targets>\n' "$(format_command "${_prefix[@]}")" "$_target_count"
}

normalize_targets() {
  local _target

  for _target in "$@"; do
    printf '%s\n' "${_target#./}"
  done | sort -u
}

collect_changed_paths() {
  local _base_commit="$1"

  {
    git diff --name-only "$_base_commit" -- 2>/dev/null
    git ls-files --others --exclude-standard 2>/dev/null
  } | sort -u
}

# Must be inside a Git repository to detect changes.
if ! GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
  emit_skip "not inside a Git repository"
  exit 0
fi
cd "$GIT_ROOT"

BASE_REF="${RUN_RELATED_TESTS_BASE_REF:-origin/main}"
if ! BASE_COMMIT=$(git merge-base HEAD "$BASE_REF" 2>/dev/null); then
  append_result git unavailable "branch base $BASE_REF" \
    "$(format_command git merge-base HEAD "$BASE_REF")" \
    "branch base reference is unavailable"
  emit_block "$RESULTS"
  exit 0
fi
CHANGED=$(collect_changed_paths "$BASE_COMMIT")
if [ -z "$CHANGED" ]; then
  emit_skip "no changes since $BASE_REF"
  exit 0
fi

# --- 1. Project extension rules: dispatch JSON-mapped tests by runner. ---
declare -a PROJECT_BATS=()
declare -a PROJECT_JS=()
declare -a PROJECT_PY=()
declare -a PROJECT_RS=()
RULES_FILE="$GIT_ROOT/.agents/hooks/rules/related_test_extensions.json"
LANGUAGE_RULES_FILE="$SCRIPT_DIR/rules/related_test_defaults.json"
if [ -f "$RULES_FILE" ] && jq empty "$RULES_FILE" 2>/dev/null; then
  mapfile -t PATTERNS < <(jq -r 'keys[]' "$RULES_FILE")
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    for pattern in "${PATTERNS[@]}"; do
      # shellcheck disable=SC2053  # intentional glob match
      if [[ "$f" == $pattern ]]; then
        while IFS= read -r t; do
          if [ -d "$t" ]; then
            PROJECT_BATS+=("$t")
            continue
          fi
          case "$t" in
            *.bats) PROJECT_BATS+=("$t") ;;
            *.py) PROJECT_PY+=("$t") ;;
            *.rs) PROJECT_RS+=("$t") ;;
            *.js | *.jsx | *.ts | *.tsx) PROJECT_JS+=("$t") ;;
          esac
        done < <(jq -r --arg k "$pattern" '.[$k][]' "$RULES_FILE")
      fi
    done
  done <<<"$CHANGED"
fi

language_rule() {
  local _language="$1"
  local _query="$2"

  # shellcheck disable=SC2016  # jq programs intentionally reference $language
  if [ -f "$LANGUAGE_RULES_FILE" ] && jq empty "$LANGUAGE_RULES_FILE" 2>/dev/null; then
    jq -r --arg language "$_language" "$_query" "$LANGUAGE_RULES_FILE"
  fi
}

has_changed_extension() {
  local _language="$1"
  local _extension
  local _path

  while IFS= read -r _extension; do
    [ -z "$_extension" ] && continue
    while IFS= read -r _path; do
      [[ "$_path" == *"$_extension" ]] && return 0
    done <<<"$CHANGED"
  done < <(language_rule "$_language" ".[\$language].source_extensions[]?")
  return 1
}

has_project_marker() {
  local _language="$1"
  local _has_markers=false

  while IFS= read -r marker; do
    [ -z "$marker" ] && continue
    _has_markers=true
    [ -f "$marker" ] && return 0
  done < <(language_rule "$_language" ".[\$language].project_markers[]?")

  [ "$_has_markers" = false ]
}

is_self_test_file() {
  local _language="$1"
  local _file="$2"
  local _name="${_file##*/}"

  while IFS= read -r extension; do
    [ -z "$extension" ] && continue
    [[ "$_file" == *"$extension" ]] && return 0
  done < <(language_rule "$_language" ".[\$language].self_test_extensions[]?")

  while IFS= read -r glob; do
    [ -z "$glob" ] && continue
    # shellcheck disable=SC2053  # intentional glob match
    [[ "$_name" == $glob ]] && return 0
  done < <(language_rule "$_language" ".[\$language].self_test_globs[]?")

  return 1
}

find_language_tests() {
  local _language="$1"
  local _stem="$2"
  local _find_args=()
  local _pattern
  local _first=true

  while IFS= read -r test_dir; do
    [ -d "$test_dir" ] || continue

    _find_args=()
    _first=true
    while IFS= read -r template; do
      [ -z "$template" ] && continue
      _pattern="${template//\{stem\}/$_stem}"
      if [ "$_first" = true ]; then
        _first=false
      else
        _find_args+=(-o)
      fi
      _find_args+=(-name "$_pattern")
    done < <(language_rule "$_language" ".[\$language].test_patterns[]?")

    [ ${#_find_args[@]} -gt 0 ] || continue

    case "$_language" in
      python)
        find "$test_dir" -type f \( "${_find_args[@]}" \) -not -path './.venv/*' -not -path './node_modules/*' 2>/dev/null
        ;;
      javascript_typescript)
        find "$test_dir" -type f \( "${_find_args[@]}" \) -not -path './node_modules/*' -not -path './.git/*' 2>/dev/null
        ;;
      *)
        find "$test_dir" -type f \( "${_find_args[@]}" \) 2>/dev/null
        ;;
    esac
  done < <(language_rule "$_language" ".[\$language].test_dirs[]?")
}

TIMEOUT_SECONDS="${RUN_RELATED_TESTS_TIMEOUT_SECONDS:-120}"

timeout_bin() {
  local _managed_timeout="${XDG_CONFIG_HOME:-$HOME/.config}/agent-harness/bin/timeout"

  if [ "${RUN_RELATED_TESTS_TIMEOUT_BIN+x}" = "x" ]; then
    command -v "$RUN_RELATED_TESTS_TIMEOUT_BIN" 2>/dev/null || return 1
    return 0
  fi
  if command -v timeout >/dev/null 2>&1; then
    command -v timeout
    return 0
  fi
  if command -v gtimeout >/dev/null 2>&1; then
    command -v gtimeout
    return 0
  fi
  if [ -x "$_managed_timeout" ]; then
    printf '%s\n' "$_managed_timeout"
    return 0
  fi
  return 1
}

run_verification() {
  local _label="$1"
  local _scope="$2"
  local _target_count="$3"
  shift 3

  local _command
  _command=$(format_command "$@")
  local _command_summary
  _command_summary=$(format_command_summary "$_target_count" "$@")

  local _timeout_bin
  if ! _timeout_bin=$(timeout_bin); then
    append_result "$_label" unavailable "$_scope" "$_command" \
      "timeout enforcement is unavailable"
    return 0
  fi

  local _output=""
  local _status=0
  _output=$("$_timeout_bin" "$TIMEOUT_SECONDS" "$@" 2>&1) || _status=$?

  if [ "$_status" -eq 0 ]; then
    append_result "$_label" passed "$_scope" "$_command_summary" ""
    return 0
  fi

  if [ "$_status" -eq 124 ]; then
    append_result "$_label" timeout "$_scope" "$_command" \
      "timed out after ${TIMEOUT_SECONDS}s${_output:+$'\n'$_output}"
    return 0
  fi

  append_result "$_label" failed "$_scope" "$_command" \
    "${_output:-exited with status $_status}"
}

require_runner() {
  local _label="$1"
  local _runner="$2"
  local _scope="$3"
  shift 3

  if command -v "$_runner" >/dev/null 2>&1; then
    return 0
  fi

  append_result "$_label" unavailable "$_scope" "$(format_command "$@")" \
    "$_runner is not available"
  return 1
}

javascript_package_manager() {
  local _declared
  _declared=$(jq -r '.packageManager // "" | split("@")[0]' package.json)
  if [ -n "$_declared" ]; then
    echo "$_declared"
    return 0
  fi

  [ -f pnpm-lock.yaml ] && echo "pnpm" && return 0
  [ -f yarn.lock ] && echo "yarn" && return 0
  { [ -f bun.lock ] || [ -f bun.lockb ]; } && echo "bun" && return 0
  echo "npm"
}

javascript_test_runner() {
  if jq -e '(.dependencies.vitest // .devDependencies.vitest // null) != null' \
    package.json >/dev/null 2>&1; then
    echo "vitest"
    return 0
  fi
  if jq -e '(.dependencies.jest // .devDependencies.jest // null) != null' \
    package.json >/dev/null 2>&1; then
    echo "jest"
    return 0
  fi
  if jq -e '
    .scripts.test
      | type == "string"
      and test("(^|[[:space:]])node[[:space:]]+--test([[:space:]]|$)")
  ' package.json >/dev/null 2>&1; then
    echo "node"
    return 0
  fi
  return 1
}

# --- 2. Bats: project rules + basename heuristic; full-suite fallback. ---
need_bats=0
has_changed_extension bats && need_bats=1
[ ${#PROJECT_BATS[@]} -gt 0 ] && need_bats=1
if [ $need_bats -eq 1 ] && [ -d tests ]; then
  BATS_BIN="${RUN_RELATED_TESTS_BATS_BIN:-bats}"
  declare -a BATS_TARGETS=()
  [ ${#PROJECT_BATS[@]} -gt 0 ] && BATS_TARGETS+=("${PROJECT_BATS[@]}")
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if is_self_test_file bats "$f" && [ -f "$f" ]; then
      BATS_TARGETS+=("$f")
      continue
    fi
    [[ "$f" == *.sh ]] || continue
    stem="${f##*/}"
    stem="${stem%.*}"
    while IFS= read -r match; do
      BATS_TARGETS+=("$match")
    done < <(find_language_tests bats "$stem")
  done <<<"$CHANGED"

  if [ ${#BATS_TARGETS[@]} -gt 0 ]; then
    mapfile -t BATS_TARGETS < <(normalize_targets "${BATS_TARGETS[@]}")
    declare -a BATS_EXIST=()
    for t in "${BATS_TARGETS[@]}"; do
      [ -e "$t" ] && BATS_EXIST+=("$t")
    done
    if [ ${#BATS_EXIST[@]} -gt 0 ]; then
      BATS_SCOPE="${#BATS_EXIST[@]} related targets"
      if require_runner bats "$BATS_BIN" "$BATS_SCOPE" \
        "$BATS_BIN" "${BATS_EXIST[@]}"; then
        run_verification bats "$BATS_SCOPE" "${#BATS_EXIST[@]}" \
          "$BATS_BIN" "${BATS_EXIST[@]}"
      fi
    else
      append_result bats unavailable "${#BATS_TARGETS[@]} related targets" \
        "$(format_command "$BATS_BIN" "${BATS_TARGETS[@]}")" \
        "selected test targets do not exist"
    fi
  elif has_changed_extension bats; then
    if require_runner bats "$BATS_BIN" "full suite" "$BATS_BIN" tests/ --recursive; then
      run_verification bats "full suite" 0 "$BATS_BIN" tests/ --recursive
    fi
  fi
fi

# --- 3. Pytest: project rules + basename heuristic; full pytest fallback. ---
need_pytest=0
has_changed_extension python && need_pytest=1
[ ${#PROJECT_PY[@]} -gt 0 ] && need_pytest=1
if [ $need_pytest -eq 1 ] && has_project_marker python; then
  declare -a PY_TARGETS=()
  [ ${#PROJECT_PY[@]} -gt 0 ] && PY_TARGETS+=("${PROJECT_PY[@]}")
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    [[ "$f" == *.py ]] || continue
    if is_self_test_file python "$f" && [ -f "$f" ]; then
      PY_TARGETS+=("$f")
      continue
    fi
    stem="${f##*/}"
    stem="${stem%.py}"
    while IFS= read -r match; do
      PY_TARGETS+=("$match")
    done < <(find_language_tests python "$stem")
  done <<<"$CHANGED"

  if [ ${#PY_TARGETS[@]} -gt 0 ]; then
    mapfile -t PY_TARGETS < <(normalize_targets "${PY_TARGETS[@]}")
    declare -a PY_EXIST=()
    for t in "${PY_TARGETS[@]}"; do
      [ -f "$t" ] && PY_EXIST+=("$t")
    done
    if [ ${#PY_EXIST[@]} -gt 0 ]; then
      PY_SCOPE="${#PY_EXIST[@]} related files"
      if require_runner pytest uv "$PY_SCOPE" \
        uv run --frozen pytest --no-header -q "${PY_EXIST[@]}"; then
        run_verification pytest "$PY_SCOPE" "${#PY_EXIST[@]}" \
          uv run --frozen pytest --no-header -q "${PY_EXIST[@]}"
      fi
    else
      append_result pytest unavailable "${#PY_TARGETS[@]} related files" \
        "$(format_command uv run --frozen pytest --no-header -q "${PY_TARGETS[@]}")" \
        "selected test targets do not exist"
    fi
  elif has_changed_extension python; then
    if require_runner pytest uv "full suite" uv run --frozen pytest --no-header -q; then
      run_verification pytest "full suite" 0 uv run --frozen pytest --no-header -q
    fi
  fi
fi

# --- 4. JavaScript and TypeScript: related tests, then the full suite. ---
need_javascript=0
has_changed_extension javascript_typescript && need_javascript=1
[ ${#PROJECT_JS[@]} -gt 0 ] && need_javascript=1
if [ $need_javascript -eq 1 ] && [ -f package.json ]; then
  declare -a JS_TARGETS=()
  declare -a JS_RELATED_SOURCES=()
  [ ${#PROJECT_JS[@]} -gt 0 ] && JS_TARGETS+=("${PROJECT_JS[@]}")
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    case "$f" in
      *.js | *.jsx | *.ts | *.tsx) ;;
      *) continue ;;
    esac
    if is_self_test_file javascript_typescript "$f" && [ -f "$f" ]; then
      JS_TARGETS+=("$f")
      continue
    fi
    [ -f "$f" ] && JS_RELATED_SOURCES+=("$f")
    stem="${f##*/}"
    stem="${stem%.*}"
    while IFS= read -r match; do
      JS_TARGETS+=("$match")
    done < <(find_language_tests javascript_typescript "$stem")
  done <<<"$CHANGED"

  JS_PACKAGE_MANAGER=$(javascript_package_manager)
  JS_RUNNER=$(javascript_test_runner || true)
  if [ -n "$JS_RUNNER" ]; then
    if [ ${#JS_TARGETS[@]} -gt 0 ]; then
      mapfile -t JS_TARGETS < <(normalize_targets "${JS_TARGETS[@]}")
    fi
    if [ ${#JS_RELATED_SOURCES[@]} -gt 0 ]; then
      mapfile -t JS_RELATED_SOURCES < <(normalize_targets "${JS_RELATED_SOURCES[@]}")
    fi

    declare -a JS_RUNNER_COMMAND=()
    declare -a JS_COMMAND=()
    case "$JS_RUNNER:$JS_PACKAGE_MANAGER" in
      node:*) JS_RUNNER_COMMAND=(node --test) ;;
      *:pnpm) JS_RUNNER_COMMAND=(pnpm exec "$JS_RUNNER") ;;
      *:npm) JS_RUNNER_COMMAND=(npm exec -- "$JS_RUNNER") ;;
      *:yarn) JS_RUNNER_COMMAND=(yarn exec "$JS_RUNNER") ;;
      *:bun) JS_RUNNER_COMMAND=(bun x "$JS_RUNNER") ;;
      *) JS_RUNNER_COMMAND=(false) ;;
    esac
    JS_EXECUTABLE="${JS_RUNNER_COMMAND[0]}"

    if [ "$JS_RUNNER" = "vitest" ]; then
      if [ ${#JS_TARGETS[@]} -gt 0 ]; then
        JS_COMMAND=("${JS_RUNNER_COMMAND[@]}" run "${JS_TARGETS[@]}")
        JS_SCOPE="${#JS_TARGETS[@]} related tests"
        if require_runner vitest "$JS_EXECUTABLE" "$JS_SCOPE" \
          env CI=1 "${JS_COMMAND[@]}"; then
          run_verification vitest "$JS_SCOPE" "${#JS_TARGETS[@]}" \
            env CI=1 "${JS_COMMAND[@]}"
        fi
      fi

      if [ ${#JS_RELATED_SOURCES[@]} -gt 0 ]; then
        JS_COMMAND=("${JS_RUNNER_COMMAND[@]}" related --run --passWithNoTests
          "${JS_RELATED_SOURCES[@]}")
        JS_SCOPE="${#JS_RELATED_SOURCES[@]} changed files"
        if require_runner vitest "$JS_EXECUTABLE" "$JS_SCOPE" \
          env CI=1 "${JS_COMMAND[@]}"; then
          run_verification vitest "$JS_SCOPE" "${#JS_RELATED_SOURCES[@]}" \
            env CI=1 "${JS_COMMAND[@]}"
        fi
      fi

      if [ ${#JS_TARGETS[@]} -eq 0 ] && [ ${#JS_RELATED_SOURCES[@]} -eq 0 ]; then
        JS_COMMAND=("${JS_RUNNER_COMMAND[@]}" run)
        if require_runner vitest "$JS_EXECUTABLE" "full suite" \
          env CI=1 "${JS_COMMAND[@]}"; then
          run_verification vitest "full suite" 0 env CI=1 "${JS_COMMAND[@]}"
        fi
      fi
    else
      JS_COMMAND=("${JS_RUNNER_COMMAND[@]}" "${JS_TARGETS[@]}")
      JS_TARGET_COUNT="${#JS_TARGETS[@]}"
      JS_SCOPE="full suite"
      [ "$JS_TARGET_COUNT" -gt 0 ] && JS_SCOPE="$JS_TARGET_COUNT related tests"
      if require_runner "$JS_RUNNER" "$JS_EXECUTABLE" "$JS_SCOPE" \
        env CI=1 "${JS_COMMAND[@]}"; then
        run_verification "$JS_RUNNER" "$JS_SCOPE" "$JS_TARGET_COUNT" \
          env CI=1 "${JS_COMMAND[@]}"
      fi
    fi
  elif jq -e '.scripts.test | type == "string" and length > 0' package.json >/dev/null 2>&1; then
    declare -a JS_COMMAND=()
    case "$JS_PACKAGE_MANAGER" in
      pnpm | npm | yarn) JS_COMMAND=("$JS_PACKAGE_MANAGER" test) ;;
      bun) JS_COMMAND=(bun run test) ;;
      *) JS_COMMAND=(false) ;;
    esac
    if require_runner "$JS_PACKAGE_MANAGER test" "${JS_COMMAND[0]}" "full suite" \
      env CI=1 "${JS_COMMAND[@]}"; then
      run_verification "$JS_PACKAGE_MANAGER test" "full suite" 0 \
        env CI=1 "${JS_COMMAND[@]}"
    fi
  else
    append_result javascript_typescript unavailable "full suite" "package test script" \
      "test command could not be determined"
  fi
fi

# --- 5. Rust: explicit project mappings, integration targets, then the full suite. ---
need_rust=0
has_changed_extension rust && need_rust=1
[ ${#PROJECT_RS[@]} -gt 0 ] && need_rust=1
if [ $need_rust -eq 1 ] && has_project_marker rust; then
  declare -a CARGO_UNIT_FILTERS=()
  declare -a CARGO_TEST_TARGETS=()
  for t in "${PROJECT_RS[@]}"; do
    [ -f "$t" ] || continue
    stem="${t##*/}"
    stem="${stem%.rs}"
    case "$t" in
      tests/*.rs) CARGO_TEST_TARGETS+=("$stem") ;;
      *) CARGO_UNIT_FILTERS+=("$stem") ;;
    esac
  done
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    [[ "$f" == *.rs ]] || continue

    stem="${f##*/}"
    stem="${stem%.rs}"
    case "$f" in
      tests/*.rs)
        CARGO_TEST_TARGETS+=("$stem")
        ;;
      src/*.rs)
        if [ -f "tests/${stem}.rs" ]; then
          CARGO_TEST_TARGETS+=("$stem")
        fi
        ;;
    esac
  done <<<"$CHANGED"

  if [ ${#CARGO_UNIT_FILTERS[@]} -eq 0 ] && [ ${#CARGO_TEST_TARGETS[@]} -eq 0 ]; then
    if require_runner rust cargo "full suite" cargo test --quiet; then
      run_verification rust "full suite" 0 cargo test --quiet
    fi
  fi

  if [ ${#CARGO_UNIT_FILTERS[@]} -gt 0 ]; then
    mapfile -t CARGO_UNIT_FILTERS < <(printf '%s\n' "${CARGO_UNIT_FILTERS[@]}" | sort -u)
    for filter in "${CARGO_UNIT_FILTERS[@]}"; do
      if require_runner rust cargo "unit filter $filter" cargo test "$filter" --quiet; then
        run_verification rust "unit filter $filter" 0 cargo test "$filter" --quiet
      fi
    done
  fi

  if [ ${#CARGO_TEST_TARGETS[@]} -gt 0 ]; then
    mapfile -t CARGO_TEST_TARGETS < <(printf '%s\n' "${CARGO_TEST_TARGETS[@]}" | sort -u)
    for target in "${CARGO_TEST_TARGETS[@]}"; do
      if require_runner rust cargo "integration target $target" \
        cargo test --test "$target" --quiet; then
        run_verification rust "integration target $target" 0 \
          cargo test --test "$target" --quiet
      fi
    done
  fi
fi

if [ "$HAS_FAILURES" -eq 1 ]; then
  emit_block "$RESULTS"
elif [ -n "$RESULTS" ]; then
  emit_success "$RESULTS"
else
  emit_skip "no related test runner matched changed paths"
fi
exit 0
