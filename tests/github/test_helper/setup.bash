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
  cat > "$GH_STUB_DIR/gh" <<'STUB'
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
  cat > "$GH_STUB_DIR/gh" <<STUB
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
    wc -l < "$GH_LOG" | tr -d ' '
  else
    echo 0
  fi
}
