#!/usr/bin/env bats
# Stop hook: differential test gate. Blocks completion when changed files'
# verification fails or is unavailable; emits {decision:"block", reason:...} JSON.
# Always exits 0 (block signal is JSON, not status).

setup() {
  load test-helper/setup
  HOOK="$HOOK_DIR/run_related_tests.sh"
  TEST_TMPDIR="$(mktemp -d "${BATS_TEST_TMPDIR:-/tmp}/gate.XXXXXX")"
  export RUN_RELATED_TESTS_BASE_REF=HEAD
}

teardown() {
  [ -d "${TEST_TMPDIR:-}" ] && rm -rf "$TEST_TMPDIR"
}

# Build a Stop event payload. Usage: make_stop_input <active>
make_stop_input() {
  local _active="${1:-false}"
  jq -n --argjson a "$_active" '{"stop_hook_active":$a,"session_id":"test"}'
}

assert_verification_passed() {
  local _message
  _message="$(jq -r '.systemMessage // empty' <<<"$output")"
  if [[ "$_message" != *'passed:'* ]]; then
    printf '%s\n' "$output"
    return 1
  fi
}

@test "run_related_tests revalidates changes when stop_hook_active is true" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin tests
  cat > bin/timeout <<'EOF'
#!/bin/bash
shift
"$@"
EOF
  cat > bin/bats <<'EOF'
#!/bin/bash
echo "revalidated after continuation"
exit 1
EOF
  chmod +x bin/timeout bin/bats
  cat > tests/script.bats <<'EOF'
@test "would fail" { false; }
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
echo hi
EOF
  git add . && git commit --quiet -m i
  printf '#!/bin/bash\necho changed\n' > script.sh
  export PATH="$TEST_TMPDIR/bin:$PATH"

  run bash "$HOOK" <<< "$(make_stop_input true)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision":"block"'* ]]
  [[ "$output" == *'revalidated after continuation'* ]]
}

@test "run_related_tests revalidates committed changes since the branch base" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin tests
  cat > bin/timeout <<'EOF'
#!/bin/bash
shift
"$@"
EOF
  cat > bin/bats <<'EOF'
#!/bin/bash
echo "committed change was verified"
exit 1
EOF
  chmod +x bin/timeout bin/bats
  cat > tests/script.bats <<'EOF'
@test "would fail" { false; }
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
echo base
EOF
  git add . && git commit --quiet -m base
  git update-ref refs/remotes/origin/main HEAD
  printf '#!/bin/bash\necho changed\n' > script.sh
  git add script.sh && git commit --quiet -m change
  export PATH="$TEST_TMPDIR/bin:$PATH"
  export RUN_RELATED_TESTS_BASE_REF=origin/main

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision":"block"'* ]]
  [[ "$output" == *'committed change was verified'* ]]
}

@test "run_related_tests blocks when the branch base is unavailable" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  touch tracked
  git add tracked && git commit --quiet -m base
  export RUN_RELATED_TESTS_BASE_REF=origin/missing

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision":"block"'* ]]
  [[ "$output" == *'unavailable: git (branch base origin/missing)'* ]]
  [[ "$output" == *'command: git merge-base HEAD origin/missing'* ]]
}

@test "run_related_tests verifies staged changes" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin tests
  cat > bin/timeout <<'EOF'
#!/bin/bash
shift
"$@"
EOF
  cat > bin/bats <<'EOF'
#!/bin/bash
echo "staged change was verified"
exit 1
EOF
  chmod +x bin/timeout bin/bats
  cat > tests/script.bats <<'EOF'
@test "would fail" { false; }
EOF
  printf '#!/bin/bash\necho base\n' > script.sh
  git add . && git commit --quiet -m base
  printf '#!/bin/bash\necho staged\n' > script.sh
  git add script.sh
  export PATH="$TEST_TMPDIR/bin:$PATH"

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision":"block"'* ]]
  [[ "$output" == *'staged change was verified'* ]]
}

@test "run_related_tests verifies untracked changes" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin tests
  cat > bin/timeout <<'EOF'
#!/bin/bash
shift
"$@"
EOF
  cat > bin/bats <<'EOF'
#!/bin/bash
echo "untracked change was verified"
exit 1
EOF
  chmod +x bin/timeout bin/bats
  cat > tests/new_script.bats <<'EOF'
@test "would fail" { false; }
EOF
  touch base
  git add . && git commit --quiet -m base
  printf '#!/bin/bash\necho untracked\n' > new_script.sh
  export PATH="$TEST_TMPDIR/bin:$PATH"

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision":"block"'* ]]
  [[ "$output" == *'untracked change was verified'* ]]
}

@test "run_related_tests reports that a non-Git directory was skipped" {
  cd "$TEST_TMPDIR"
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  message="$(jq -r '.systemMessage' <<<"$output")"
  [[ "$message" == *'skipped: not inside a Git repository'* ]]
}

@test "run_related_tests reports when there are no branch changes" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  touch f && git add f && git commit --quiet -m i
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  message="$(jq -r '.systemMessage' <<<"$output")"
  [[ "$message" == *'skipped: no changes since HEAD'* ]]
}

@test "run_related_tests reports when no related test runner is detected" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  touch base && git add base && git commit --quiet -m i
  printf 'console.log(1)\n' > app.js  # untracked change, no test framework
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  message="$(jq -r '.systemMessage' <<<"$output")"
  [[ "$message" == *'skipped: no related test runner matched changed paths'* ]]
}

@test "run_related_tests does not treat JSON as JavaScript" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  cat > package.json <<'EOF'
{
  "scripts": {}
}
EOF
  printf '{"enabled":true}\n' > settings.json
  git add . && git commit --quiet -m i
  printf '\n' >> settings.json

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  message="$(jq -r '.systemMessage' <<<"$output")"
  [[ "$message" == *'skipped: no related test runner matched changed paths'* ]]
}

@test "run_related_tests blocks when a JavaScript project has no test command" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir src
  cat > package.json <<'EOF'
{
  "scripts": {}
}
EOF
  printf 'export const value = 1\n' > src/app.ts
  git add . && git commit --quiet -m i
  printf '\n' >> src/app.ts

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision":"block"'* ]]
  [[ "$output" == *'unavailable: javascript_typescript (full suite)'* ]]
  [[ "$output" == *'result: test command could not be determined'* ]]
}

@test "run_related_tests emits block JSON when bats tests fail" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir tests
  cat > tests/sample.bats <<'EOF'
@test "always fails" {
  false
}
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
echo hi
EOF
  git add . && git commit --quiet -m i
  printf '#!/bin/bash\necho changed\n' > script.sh
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision"'* ]]
  [[ "$output" == *'block'* ]]
  [[ "$output" == *'failed: bats (full suite)'* ]]
  [[ "$output" == *'command: bats tests/ --recursive'* ]]
}

@test "run_related_tests limits failed verification output" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin tests
  cat > bin/timeout <<'EOF'
#!/bin/bash
shift
"$@"
EOF
  cat > bin/bats <<'EOF'
#!/bin/bash
line=1
while [ "$line" -le 60 ]; do
  printf 'failure line %02d\n' "$line"
  line=$((line + 1))
done
exit 1
EOF
  chmod +x bin/timeout bin/bats
  export PATH="$TEST_TMPDIR/bin:$PATH"
  printf '@test "fails" { false; }\n' > tests/script.bats
  printf '#!/bin/bash\n' > script.sh
  git add . && git commit --quiet -m i
  printf '\n' >> script.sh

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'failed: bats (1 related targets)'* ]]
  [[ "$output" == *'command: bats tests/script.bats'* ]]
  [[ "$output" == *'[output truncated'* ]]
  ! [[ "$output" == *'failure line 01'* ]]
  [[ "$output" == *'failure line 60'* ]]
}

@test "run_related_tests blocks when a required runner is unavailable" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir tests
  cat > tests/script.bats <<'EOF'
@test "would pass" { true; }
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
echo hi
EOF
  git add . && git commit --quiet -m i
  printf '#!/bin/bash\necho changed\n' > script.sh
  export RUN_RELATED_TESTS_BATS_BIN=missing-bats-runner

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision":"block"'* ]]
  [[ "$output" == *'unavailable: bats (1 related targets)'* ]]
  [[ "$output" == *'result: missing-bats-runner is not available'* ]]
}

@test "run_related_tests blocks when timeout enforcement is unavailable" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin tests
  cat > bin/bats <<'EOF'
#!/bin/bash
exit 0
EOF
  chmod +x bin/bats
  cat > tests/script.bats <<'EOF'
@test "would pass" { true; }
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
echo hi
EOF
  git add . && git commit --quiet -m i
  printf '#!/bin/bash\necho changed\n' > script.sh
  export PATH="$TEST_TMPDIR/bin:$PATH"
  export RUN_RELATED_TESTS_TIMEOUT_BIN=missing-timeout-runner

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision":"block"'* ]]
  [[ "$output" == *'unavailable: bats (1 related targets)'* ]]
  [[ "$output" == *'result: timeout enforcement is unavailable'* ]]
}

@test "run_related_tests uses the Home Manager timeout outside PATH" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin home/.config/agent-harness/bin tests
  for _dependency in bash dirname find grep jq rm sort; do
    ln -s "$(command -v "$_dependency")" "bin/$_dependency"
  done
  cat > bin/git <<EOF
#!/bin/bash
case "\$*" in
  "rev-parse --show-toplevel") printf '%s\n' "$TEST_TMPDIR" ;;
  "merge-base HEAD HEAD") printf '%s\n' base ;;
  "diff --name-only base --") printf '%s\n' script.sh ;;
  "ls-files --others --exclude-standard") exit 0 ;;
  *) exit 1 ;;
esac
EOF
  cat > home/.config/agent-harness/bin/timeout <<'EOF'
#!/bin/bash
shift
"$@"
EOF
  cat > bin/bats <<'EOF'
#!/bin/bash
exit 0
EOF
  chmod +x home/.config/agent-harness/bin/timeout bin/bats bin/git
  cat > tests/script.bats <<'EOF'
@test "would pass" { true; }
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
echo hi
EOF
  git add . && git commit --quiet -m i
  printf '#!/bin/bash\necho changed\n' > script.sh
  export XDG_CONFIG_HOME="$TEST_TMPDIR/home/.config"
  export PATH="$TEST_TMPDIR/bin"

  run bash "$HOOK" <<< '{"stop_hook_active":false,"session_id":"test"}'

  [ "$status" -eq 0 ]
  assert_verification_passed
}

@test "run_related_tests blocks when bats runner times out" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin tests
  cat > bin/timeout <<'EOF'
#!/bin/bash
exit 124
EOF
  cat > bin/bats <<'EOF'
#!/bin/bash
exit 0
EOF
  chmod +x bin/timeout bin/bats
  cat > tests/script.bats <<'EOF'
@test "would pass" { true; }
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
echo hi
EOF
  git add . && git commit --quiet -m i
  printf '#!/bin/bash\necho changed\n' > script.sh
  export PATH="$TEST_TMPDIR/bin:$PATH"
  export RUN_RELATED_TESTS_TIMEOUT_SECONDS=1

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision"'* ]]
  [[ "$output" == *'timeout: bats (1 related targets)'* ]]
  [[ "$output" == *'timed out after 1s'* ]]
}

@test "run_related_tests reports successful Bats verification" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir tests
  cat > tests/sample.bats <<'EOF'
@test "trivially passes" {
  true
}
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
echo hi
EOF
  git add . && git commit --quiet -m i
  printf '#!/bin/bash\necho changed\n' > script.sh
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  message="$(jq -r '.systemMessage' <<<"$output")"
  [[ "$message" == *'passed: bats (full suite)'* ]]
  [[ "$message" == *'command: bats tests/ --recursive'* ]]
}

# --- project extension rules file (.agents/hooks/rules/related_test_extensions.json) ---

@test "run_related_tests runs tests mapped by JSON rules and blocks on failure" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p .agents/hooks/rules tests lib
  cat > .agents/hooks/rules/related_test_extensions.json <<'EOF'
{
  "lib/shared.sh": ["tests/fan_out.bats"]
}
EOF
  # Fan-out target fails — the wrapper must pick it via JSON, not basename.
  cat > tests/fan_out.bats <<'EOF'
@test "fan-out target fails" { false; }
EOF
  cat > tests/other.bats <<'EOF'
@test "unrelated passes" { true; }
EOF
  cat > lib/shared.sh <<'EOF'
#!/bin/bash
EOF
  git add . && git commit --quiet -m i
  printf 'changed\n' >> lib/shared.sh
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision"'* ]]
  [[ "$output" == *'block'* ]]
  [[ "$output" == *'fan-out target fails'* ]]
}

@test "run_related_tests reports successful JSON-mapped tests" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p .agents/hooks/rules tests lib
  cat > .agents/hooks/rules/related_test_extensions.json <<'EOF'
{
  "lib/shared.sh": ["tests/fan_out.bats"]
}
EOF
  cat > tests/fan_out.bats <<'EOF'
@test "fan-out target passes" { true; }
EOF
  cat > lib/shared.sh <<'EOF'
#!/bin/bash
EOF
  git add . && git commit --quiet -m i
  printf 'changed\n' >> lib/shared.sh
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  assert_verification_passed
}

@test "run_related_tests combines JSON rules with basename heuristic" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p .agents/hooks/rules tests
  # JSON contributes a fan-out target; basename heuristic contributes
  # tests/script.bats. Both must run.
  cat > .agents/hooks/rules/related_test_extensions.json <<'EOF'
{
  "script.sh": ["tests/extra.bats"]
}
EOF
  cat > tests/script.bats <<'EOF'
@test "basename match passes" { true; }
EOF
  cat > tests/extra.bats <<'EOF'
@test "extra fan-out fails" { false; }
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
EOF
  git add . && git commit --quiet -m i
  printf 'changed\n' >> script.sh
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  [[ "$output" == *'extra fan-out fails'* ]]
  [[ "$output" == *'"decision"'* ]]
}

@test "run_related_tests ignores invalid JSON and falls back to heuristic" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p .agents/hooks/rules tests
  printf 'not valid json {{{\n' > .agents/hooks/rules/related_test_extensions.json
  cat > tests/script.bats <<'EOF'
@test "basename heuristic still runs" { true; }
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
EOF
  git add . && git commit --quiet -m i
  printf 'changed\n' >> script.sh
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  assert_verification_passed
}

@test "run_related_tests matches JSON glob patterns" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p .agents/hooks/rules tests config
  cat > .agents/hooks/rules/related_test_extensions.json <<'EOF'
{
  "config/*.toml": ["tests/config_check.bats"]
}
EOF
  cat > tests/config_check.bats <<'EOF'
@test "config check fails" { false; }
EOF
  cat > config/app.toml <<'EOF'
key = "value"
EOF
  git add . && git commit --quiet -m i
  printf '\nupdated = true\n' >> config/app.toml
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  [[ "$output" == *'config check fails'* ]]
}

@test "run_related_tests runs a Bats directory mapped by JSON rules" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p .agents/hooks/rules bin nix tests/nix
  cat > .agents/hooks/rules/related_test_extensions.json <<'EOF'
{
  "nix/**": ["tests/nix"]
}
EOF
  cat > bin/timeout <<'EOF'
#!/bin/bash
shift
"$@"
EOF
  cat > bin/bats <<'EOF'
#!/bin/bash
printf '%s\n' "$*" > bats_args.txt
exit 0
EOF
  chmod +x bin/timeout bin/bats
  cat > tests/nix/module.bats <<'EOF'
@test "module passes" { true; }
EOF
  printf '{ }\n' > nix/module.nix
  git add . && git commit --quiet -m base
  printf '\n' >> nix/module.nix
  export PATH="$TEST_TMPDIR/bin:$PATH"

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [ "$(cat bats_args.txt)" = "tests/nix" ]
}

@test "run_related_tests runs Rust integration tests mapped from non-Rust changes" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p .agents/hooks/rules bin nix tests
  cat > .agents/hooks/rules/related_test_extensions.json <<'EOF'
{
  "nix/*.nix": ["tests/claude_materialization.rs"]
}
EOF
  cat > bin/cargo <<'EOF'
#!/bin/bash
printf '%s\n' "$*" > cargo_args.txt
exit 0
EOF
  chmod +x bin/cargo
  export PATH="$TEST_TMPDIR/bin:$PATH"
  touch Cargo.toml
  printf '{ }\n' > nix/module.nix
  printf '#[test]\nfn materializes() {}\n' > tests/claude_materialization.rs
  git add . && git commit --quiet -m i
  printf '\n' >> nix/module.nix

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  assert_verification_passed
  [ "$(cat cargo_args.txt)" = "test --test claude_materialization --quiet" ]
}

# --- basename heuristic fallback ---

@test "run_related_tests runs only matching bats file when basename matches" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir tests
  # Matching test for script.sh — must pass.
  cat > tests/script.bats <<'EOF'
@test "script test passes" {
  true
}
EOF
  # Unrelated failing test — must NOT be selected by the basename heuristic.
  cat > tests/other.bats <<'EOF'
@test "other test fails" {
  false
}
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
EOF
  git add . && git commit --quiet -m i
  printf 'changed\n' >> script.sh
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  assert_verification_passed
}

@test "run_related_tests falls back to full bats when basename does not match" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir tests
  # No basename match for unrelated.sh exists; the unrelated failing test
  # must be picked up by the full-suite fallback.
  cat > tests/other.bats <<'EOF'
@test "other test fails" {
  false
}
EOF
  cat > unrelated.sh <<'EOF'
#!/bin/bash
EOF
  git add . && git commit --quiet -m i
  printf 'changed\n' >> unrelated.sh
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision"'* ]]
  [[ "$output" == *'block'* ]]
}

@test "run_related_tests matches test_<stem>.bats convention" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir tests
  cat > tests/test_script.bats <<'EOF'
@test "script test passes" {
  true
}
EOF
  cat > tests/other.bats <<'EOF'
@test "other test fails" {
  false
}
EOF
  cat > script.sh <<'EOF'
#!/bin/bash
EOF
  git add . && git commit --quiet -m i
  printf 'changed\n' >> script.sh
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  assert_verification_passed
}

@test "run_related_tests runs the changed bats file itself" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir tests
  cat > tests/changed.bats <<'EOF'
@test "passes" { true; }
EOF
  cat > tests/other.bats <<'EOF'
@test "other fails" { false; }
EOF
  git add . && git commit --quiet -m i
  printf '\n@test "still passes" { true; }\n' >> tests/changed.bats
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  assert_verification_passed
}

@test "run_related_tests matches python test_<stem>.py convention from default rules" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin
  cat > bin/uv <<'EOF'
#!/bin/bash
case "$*" in
*"test_other.py"*)
  echo "unexpected unrelated test"
  exit 1
  ;;
*)
  exit 0
  ;;
esac
EOF
  chmod +x bin/uv
  export PATH="$TEST_TMPDIR/bin:$PATH"
  touch pyproject.toml
  mkdir tests
  cat > app.py <<'EOF'
def value():
    return 1
EOF
  cat > tests/test_app.py <<'EOF'
def test_value():
    assert True
EOF
  cat > tests/test_other.py <<'EOF'
def test_other():
    assert False
EOF
  git add . && git commit --quiet -m i
  printf '\n' >> app.py
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  assert_verification_passed
}

@test "run_related_tests normalizes duplicate pytest target paths" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p .agents/hooks/rules bin tests
  cat > .agents/hooks/rules/related_test_extensions.json <<'EOF'
{
  "app.py": ["tests/test_app.py"]
}
EOF
  cat > bin/uv <<'EOF'
#!/bin/bash
printf '%s\n' "$*" > uv_args.txt
exit 0
EOF
  chmod +x bin/uv
  export PATH="$TEST_TMPDIR/bin:$PATH"
  touch pyproject.toml
  printf 'def value():\n    return 1\n' > app.py
  printf 'def test_value():\n    assert True\n' > tests/test_app.py
  git add . && git commit --quiet -m i
  printf '\n' >> app.py

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  [ "$(cat uv_args.txt)" = \
    "run --frozen pytest --no-header -q tests/test_app.py" ]
}

@test "run_related_tests summarizes successful pytest targets" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p .agents/hooks/rules bin config tests
  cat > .agents/hooks/rules/related_test_extensions.json <<'EOF'
{
  "config/*.toml": ["tests/test_first.py", "tests/test_second.py"]
}
EOF
  cat > bin/uv <<'EOF'
#!/bin/bash
exit 0
EOF
  chmod +x bin/uv
  export PATH="$TEST_TMPDIR/bin:$PATH"
  touch pyproject.toml tests/test_first.py tests/test_second.py
  printf 'enabled = true\n' > config/app.toml
  git add . && git commit --quiet -m i
  printf '\n' >> config/app.toml

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  message="$(jq -r '.systemMessage' <<<"$output")"
  [[ "$message" == *'passed: pytest (2 related files)'* ]]
  [[ "$message" == *'command: uv run --frozen pytest --no-header -q <2 targets>'* ]]
  ! [[ "$message" == *'tests/test_first.py'* ]]
  ! [[ "$message" == *'runner:'* ]]
  ! [[ "$message" == *'target:'* ]]
}

@test "run_related_tests matches python <stem>_test.py convention from default rules" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin
  cat > bin/uv <<'EOF'
#!/bin/bash
echo "test_value"
exit 1
EOF
  chmod +x bin/uv
  export PATH="$TEST_TMPDIR/bin:$PATH"
  touch pyproject.toml
  mkdir tests
  cat > service.py <<'EOF'
def value():
    return 1
EOF
  cat > tests/service_test.py <<'EOF'
def test_value():
    assert False
EOF
  git add . && git commit --quiet -m i
  printf '\n' >> service.py
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision"'* ]]
  [[ "$output" == *'test_value'* ]]
}

@test "run_related_tests runs named and import-related Vitest tests" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin src tests
  cat > bin/pnpm <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> pnpm_args.txt
exit 0
EOF
  chmod +x bin/pnpm
  export PATH="$TEST_TMPDIR/bin:$PATH"
  cat > package.json <<'EOF'
{
  "packageManager": "pnpm@10.0.0",
  "devDependencies": { "vitest": "1.0.0" },
  "scripts": { "test": "vitest run" }
}
EOF
  printf 'export const value = 1\n' > src/app.ts
  printf 'test("value", () => {})\n' > tests/app.test.ts
  git add . && git commit --quiet -m i
  printf '\n' >> src/app.ts

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  assert_verification_passed
  [ "$(cat pnpm_args.txt)" = $'exec vitest run tests/app.test.ts\nexec vitest related --run --passWithNoTests src/app.ts' ]
}

@test "run_related_tests uses Vitest related without a named test" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin src tests
  cat > bin/pnpm <<'EOF'
#!/bin/bash
printf '%s\n' "$*" > pnpm_args.txt
exit 0
EOF
  chmod +x bin/pnpm
  export PATH="$TEST_TMPDIR/bin:$PATH"
  cat > package.json <<'EOF'
{
  "packageManager": "pnpm@10.0.0",
  "devDependencies": { "vitest": "1.0.0" },
  "scripts": { "test": "vitest run" }
}
EOF
  printf 'export const value = 1\n' > src/app.ts
  printf 'test("other", () => {})\n' > tests/other.test.ts
  git add . && git commit --quiet -m i
  printf '\n' >> src/app.ts

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  assert_verification_passed
  [ "$(cat pnpm_args.txt)" = \
    "exec vitest related --run --passWithNoTests src/app.ts" ]
}

@test "run_related_tests falls back to the declared JavaScript test script" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin src
  cat > bin/pnpm <<'EOF'
#!/bin/bash
printf '%s:%s\n' "$CI" "$*" > pnpm_args.txt
exit 0
EOF
  chmod +x bin/pnpm
  export PATH="$TEST_TMPDIR/bin:$PATH"
  cat > package.json <<'EOF'
{
  "packageManager": "pnpm@10.0.0",
  "scripts": { "test": "custom-test-runner" }
}
EOF
  printf 'export const value = 1\n' > src/app.ts
  git add . && git commit --quiet -m i
  printf '\n' >> src/app.ts

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  assert_verification_passed
  [ "$(cat pnpm_args.txt)" = "1:test" ]
}

@test "run_related_tests runs the related Jest file with npm" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin src tests
  cat > bin/npm <<'EOF'
#!/bin/bash
printf '%s\n' "$*" > npm_args.txt
exit 0
EOF
  chmod +x bin/npm
  export PATH="$TEST_TMPDIR/bin:$PATH"
  cat > package.json <<'EOF'
{
  "packageManager": "npm@11.0.0",
  "devDependencies": { "jest": "30.0.0" },
  "scripts": { "test": "jest" }
}
EOF
  printf 'export const value = 1\n' > src/app.js
  printf 'test("value", () => {})\n' > tests/app.spec.js
  git add . && git commit --quiet -m i
  printf '\n' >> src/app.js

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  assert_verification_passed
  [ "$(cat npm_args.txt)" = "exec -- jest tests/app.spec.js" ]
}

@test "run_related_tests runs the related Node test file" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin src tests
  cat > bin/node <<'EOF'
#!/bin/bash
printf '%s\n' "$*" > node_args.txt
exit 0
EOF
  chmod +x bin/node
  export PATH="$TEST_TMPDIR/bin:$PATH"
  cat > package.json <<'EOF'
{
  "scripts": { "test": "node --test" }
}
EOF
  printf 'export const value = 1\n' > src/app.js
  printf 'import test from "node:test"\n' > tests/app.test.js
  git add . && git commit --quiet -m i
  printf '\n' >> src/app.js

  run bash "$HOOK" <<< "$(make_stop_input false)"

  [ "$status" -eq 0 ]
  assert_verification_passed
  [ "$(cat node_args.txt)" = "--test tests/app.test.js" ]
}

@test "run_related_tests runs changed Rust integration test target" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin tests
  cat > bin/cargo <<'EOF'
#!/bin/bash
printf '%s\n' "$*" > cargo_args.txt
exit 0
EOF
  chmod +x bin/cargo
  export PATH="$TEST_TMPDIR/bin:$PATH"
  touch Cargo.toml
  cat > tests/parser.rs <<'EOF'
#[test]
fn parses() {}
EOF
  git add . && git commit --quiet -m i
  printf '\n' >> tests/parser.rs
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  assert_verification_passed
  [ "$(cat cargo_args.txt)" = "test --test parser --quiet" ]
}

@test "run_related_tests runs matching Rust integration test for changed source" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin src tests
  cat > bin/cargo <<'EOF'
#!/bin/bash
echo "parser integration failed"
exit 1
EOF
  chmod +x bin/cargo
  export PATH="$TEST_TMPDIR/bin:$PATH"
  touch Cargo.toml
  cat > src/parser.rs <<'EOF'
pub fn parse() {}
EOF
  cat > tests/parser.rs <<'EOF'
#[test]
fn parses() {}
EOF
  git add . && git commit --quiet -m i
  printf '\n' >> src/parser.rs
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision"'* ]]
  [[ "$output" == *'cargo test --test parser'* ]]
  [[ "$output" == *'parser integration failed'* ]]
}

@test "run_related_tests falls back to the full Rust suite without a matching integration test" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin src tests
  cat > bin/cargo <<'EOF'
#!/bin/bash
printf '%s\n' "$*" > cargo_args.txt
exit 0
EOF
  chmod +x bin/cargo
  export PATH="$TEST_TMPDIR/bin:$PATH"
  touch Cargo.toml
  cat > src/parser.rs <<'EOF'
pub fn parse() {}
EOF
  cat > tests/other.rs <<'EOF'
#[test]
fn other() {}
EOF
  git add . && git commit --quiet -m i
  printf '\n' >> src/parser.rs
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  assert_verification_passed
  [ "$(cat cargo_args.txt)" = "test --quiet" ]
}

@test "run_related_tests falls back to the full Rust suite for generic source stems" {
  cd "$TEST_TMPDIR"
  git init --quiet
  git config user.email t@t
  git config user.name t
  git config commit.gpgsign false
  mkdir -p bin src
  cat > bin/cargo <<'EOF'
#!/bin/bash
printf '%s\n' "$*" > cargo_args.txt
exit 0
EOF
  chmod +x bin/cargo
  export PATH="$TEST_TMPDIR/bin:$PATH"
  touch Cargo.toml
  cat > src/lib.rs <<'EOF'
pub fn parse() {}
EOF
  git add . && git commit --quiet -m i
  printf '\n' >> src/lib.rs
  run bash "$HOOK" <<< "$(make_stop_input false)"
  [ "$status" -eq 0 ]
  assert_verification_passed
  [ "$(cat cargo_args.txt)" = "test --quiet" ]
}
