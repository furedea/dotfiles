# Shared setup for github script tests.

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
GITHUB_DIR="$REPO_ROOT/github"
SCRIPT="$GITHUB_DIR/setup_repo.sh"

# Create a stub gh command that logs calls to a file for assertion.
# The stub succeeds by default and records each invocation.
setup_gh_stub() {
  GH_LOG="$BATS_TEST_TMPDIR/gh_calls.log"
  GH_STUB_DIR="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$GH_STUB_DIR"
  cat >"$GH_STUB_DIR/gh" <<'STUB'
#!/bin/bash
echo "$*" >> "${GH_LOG}"
# For "repo view" subcommand, return a fake owner/repo
if [[ "$1" == "repo" && "$2" == "view" ]]; then
  echo "detected/repo"
fi
STUB
  chmod +x "$GH_STUB_DIR/gh"
  export PATH="$GH_STUB_DIR:$PATH"
  export GH_LOG
}

# Replace the default stub with one that reports an existing ruleset id
# for the list query, exercising the PUT (update) path.
setup_gh_stub_with_existing_ruleset() {
  local _id="$1"
  cat >"$GH_STUB_DIR/gh" <<STUB
#!/bin/bash
echo "\$*" >> "${GH_LOG}"
if [[ "\$1" == "repo" && "\$2" == "view" ]]; then
  echo "detected/repo"
fi
if [[ "\$*" == *"/rulesets --jq"* ]]; then
  echo "${_id}"
fi
STUB
  chmod +x "$GH_STUB_DIR/gh"
}

# Read all gh calls from the log.
gh_calls() {
  cat "$GH_LOG" 2>/dev/null || true
}

# Count how many times gh was called.
gh_call_count() {
  if [[ -f "$GH_LOG" ]]; then
    wc -l <"$GH_LOG" | tr -d ' '
  else
    echo 0
  fi
}

# Create gh and ghq stubs for github/create_repo.sh tests.
setup_create_repo_stubs() {
  GH_LOG="$BATS_TEST_TMPDIR/gh_calls.log"
  GH_STUB_DIR="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$GH_STUB_DIR"
  cat >"$GH_STUB_DIR/ghq" <<'STUB'
#!/bin/bash
if [[ "$1" == "root" ]]; then
  echo "${BATS_TEST_TMPDIR}/ghq"
  exit 0
fi
echo "unexpected ghq call: $*" >&2
exit 1
STUB
  cat >"$GH_STUB_DIR/gh" <<'STUB'
#!/bin/bash
echo "$*" >> "${GH_LOG}"

if [[ "$1" == "api" && "$2" == "user" ]]; then
  echo "furedea"
  exit 0
fi

if [[ "$1" == "api" && "$2" == repos/* && "$2" != */git/ref/* && "$*" == *"--jq .default_branch"* ]]; then
  echo "main"
  exit 0
fi

if [[ "$1" == "api" && "$2" == repos/*/git/ref/heads/* ]]; then
  if [[ "${GH_REF_EMPTY_ONCE:-}" == "1" && ! -f "${BATS_TEST_TMPDIR}/ref_ready" ]]; then
    touch "${BATS_TEST_TMPDIR}/ref_ready"
    echo '{"message":"Git Repository is empty.","status":"409"}'
    exit 1
  fi
  echo "refs/heads/main"
  exit 0
fi

if [[ "$1" == "api" && "$2" == */rulesets && "$*" == *"--jq"* ]]; then
  exit 0
fi

if [[ "$1" == "repo" && "$2" == "clone" ]]; then
  mkdir -p "$4/src"
  cat > "$4/Cargo.toml" <<'EOF'
[package]
name = "template-rust"
version = "0.1.0"
edition = "2024"
EOF
  touch "$4/flake.nix" "$4/.envrc" "$4/src/main.rs"
  exit 0
fi

exit 0
STUB
  cat >"$GH_STUB_DIR/sleep" <<'STUB'
#!/bin/bash
exit 0
STUB
  chmod +x "$GH_STUB_DIR/gh" "$GH_STUB_DIR/ghq" "$GH_STUB_DIR/sleep"
  export PATH="$GH_STUB_DIR:$PATH"
  export GH_LOG
}
