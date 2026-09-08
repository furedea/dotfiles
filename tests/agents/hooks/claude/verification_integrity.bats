#!/usr/bin/env bats
# Verification must not accept missing evidence as a successful gate.
# Each Bats test intentionally owns its runner output environment.
# shellcheck disable=SC2030,SC2031

setup() {
  load test-helper/setup
  HOOK="$HOOK_DIR/run_related_tests.sh"
  create_temp_git_repo
  cd "$TEMP_REPO" || return
  export RUN_RELATED_TESTS_BASE_REF=HEAD
  export RUN_RELATED_TESTS_REUSE=0
  export XDG_STATE_HOME="$BATS_TEST_TMPDIR/state"
  mkdir -p bin tests .agents/hooks/rules
  export PATH="$TEMP_REPO/bin:$PATH"
  printf '#!/usr/bin/env bash\nshift\n"$@"\n' >bin/timeout
  # shellcheck disable=SC2016 # Expanded by the stub, not by fixture creation.
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" "${TEST_RUNNER_OUTPUT:-1 passed}"\n' >bin/uv
  cp bin/uv bin/cargo
  cp bin/uv bin/pnpm
  cp bin/uv bin/bats
  chmod +x bin/timeout bin/uv bin/cargo bin/pnpm bin/bats
}

assert_incomplete() {
  [ "$status" -eq 0 ]
  [ "$(jq -r '.decision' <<<"$output")" = block ]
  [[ "$output" != *"Verification passed"* ]]
}

@test "Bats suite receives a longer default budget while explicit timeout wins" {
  touch tests/source.bats
  export TEST_RUNNER_OUTPUT=$'1..1\nok 1 source'
  # Record the budget without waiting for it to elapse.
  # shellcheck disable=SC2016 # Expanded by the timeout stub.
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$1" > "$BATS_TEST_TMPDIR/budget"\nshift\n"$@"\n' >bin/timeout
  unset RUN_RELATED_TESTS_TIMEOUT_SECONDS

  run bash "$HOOK"

  [ "$status" -eq 0 ]
  [[ "$output" == *"Verification passed"* ]]
  [ "$(cat "$BATS_TEST_TMPDIR/budget")" = 300 ]

  export RUN_RELATED_TESTS_TIMEOUT_SECONDS=7
  run bash "$HOOK"

  [ "$status" -eq 0 ]
  [[ "$output" == *"Verification passed"* ]]
  [ "$(cat "$BATS_TEST_TMPDIR/budget")" = 7 ]
}

@test "non-Bats verification retains the existing default timeout" {
  touch pyproject.toml tests/test_source.py
  # shellcheck disable=SC2016 # Expanded by the timeout stub.
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$1" > "$BATS_TEST_TMPDIR/budget"\nshift\n"$@"\n' >bin/timeout
  unset RUN_RELATED_TESTS_TIMEOUT_SECONDS

  run bash "$HOOK"

  [ "$status" -eq 0 ]
  [[ "$output" == *"Verification passed"* ]]
  [ "$(cat "$BATS_TEST_TMPDIR/budget")" = 120 ]
}

@test "explicit missing test is reported even when another target exists" {
  touch pyproject.toml source.py tests/test_source.py
  printf '%s\n' '{"source.py":["tests/test_source.py","tests/test_missing.py"]}' >.agents/hooks/rules/related_test_extensions.json

  run bash "$HOOK"

  assert_incomplete
  [[ "$output" == *"tests/test_missing.py"* ]]
}

@test "invalid project JSON is not treated as absent configuration" {
  touch source.py pyproject.toml tests/test_source.py
  printf '{broken' >.agents/hooks/rules/related_test_extensions.json

  run bash "$HOOK"

  assert_incomplete
  [[ "$output" == *"configuration"* ]]
}

@test "project mapping values must be arrays of nonempty paths" {
  touch source.py pyproject.toml
  printf '%s\n' '{"source.py":"tests/test_source.py"}' >.agents/hooks/rules/related_test_extensions.json

  run bash "$HOOK"

  assert_incomplete
  [[ "$output" == *"configuration"* ]]
}

@test "missing required default rules are reported" {
  mkdir -p "$BATS_TEST_TMPDIR/hooks"
  cp "$HOOK" "$BATS_TEST_TMPDIR/hooks/run_related_tests.sh"
  touch source.py pyproject.toml

  run bash "$BATS_TEST_TMPDIR/hooks/run_related_tests.sh"

  assert_incomplete
  [[ "$output" == *"related_test_defaults.json"* ]]
}

@test "explicit Rust filter with no executed tests is incomplete" {
  touch Cargo.toml source.rs
  printf '%s\n' '{"source.rs":["source.rs"]}' >.agents/hooks/rules/related_test_extensions.json
  export TEST_RUNNER_OUTPUT='test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 12 filtered out; finished in 0.00s'

  run bash "$HOOK"

  assert_incomplete
  [[ "$output" == *"No tests executed"* ]]
}

@test "all skipped pytest tests are not successful verification" {
  touch pyproject.toml tests/test_source.py
  export TEST_RUNNER_OUTPUT='3 skipped in 0.01s'

  run bash "$HOOK"

  assert_incomplete
  [[ "$output" == *"No tests executed"* ]]
}

@test "Rust summaries are combined instead of rejecting an empty doc test phase" {
  touch Cargo.toml source.rs
  export TEST_RUNNER_OUTPUT=$'test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s'

  run bash "$HOOK"

  [ "$status" -eq 0 ]
  [[ "$output" == *"Verification passed"* ]]
}

@test "unknown test counts are not guessed to be zero" {
  touch pyproject.toml tests/test_source.py
  export TEST_RUNNER_OUTPUT='custom runner finished successfully'

  run bash "$HOOK"

  [ "$status" -eq 0 ]
  [[ "$output" == *"test count unavailable"* ]]
}

@test "all skipped Bats tests are incomplete" {
  touch tests/source.bats
  export TEST_RUNNER_OUTPUT=$'1..1\nok 1 source # skip unavailable service'

  run bash "$HOOK"

  assert_incomplete
  [[ "$output" == *"No tests executed"* ]]
}

@test "Vitest discovery without related tests is skipped rather than passed" {
  printf '%s\n' '{"packageManager":"pnpm@10","devDependencies":{"vitest":"1"}}' >package.json
  touch source.ts
  export TEST_RUNNER_OUTPUT='No test files found, exiting with code 0'

  run bash "$HOOK"

  [ "$status" -eq 0 ]
  [[ "$output" == *"Verification skipped"* ]]
  [[ "$output" != *"Verification passed"* ]]
}

@test "all skipped Vitest tests are incomplete even in discovery mode" {
  printf '%s\n' '{"packageManager":"pnpm@10","devDependencies":{"vitest":"1"}}' >package.json
  touch source.ts
  export TEST_RUNNER_OUTPUT='Tests  2 skipped (2)'

  run bash "$HOOK"

  assert_incomplete
}

@test "an explicit test target with no runner configuration is incomplete" {
  touch source.md tests/test_source.py
  printf '%s\n' '{"source.md":["tests/test_source.py"]}' >.agents/hooks/rules/related_test_extensions.json

  run bash "$HOOK"

  assert_incomplete
}
