# Fixtures for Zsh repository search tests.

function setup_repository_search_fixture() {
  local _fixture_root
  _fixture_root="$(cd "$BATS_FILE_TMPDIR" && pwd -P)"
  TEST_REPOSITORY="$_fixture_root/ghq/github.com/example/repository"
  TEST_WORKTREE="$_fixture_root/worktrees/repository-feature"

  mkdir -p "$TEST_REPOSITORY"
  git -C "$TEST_REPOSITORY" init --quiet --initial-branch=main
  git -C "$TEST_REPOSITORY" config user.email test@example.com
  git -C "$TEST_REPOSITORY" config user.name Test
  git -C "$TEST_REPOSITORY" config commit.gpgsign false
  git -C "$TEST_REPOSITORY" config core.fsmonitor false
  git -C "$TEST_REPOSITORY" config core.hooksPath /dev/null
  : >"$TEST_REPOSITORY/README.md"
  git -C "$TEST_REPOSITORY" add README.md
  git -C "$TEST_REPOSITORY" commit --quiet -m initial
  git -C "$TEST_REPOSITORY" worktree add --quiet -b feature "$TEST_WORKTREE"

  export TEST_REPOSITORY
  export TEST_WORKTREE
}

function setup_repository_search_stubs() {
  cat >"$TEST_BIN/ghq" <<'EOF'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
set +x

[[ "$*" == "list -p" ]]
printf '%s\n' "$TEST_REPOSITORY"
if [[ "${GHQ_INCLUDES_WORKTREE:-false}" == true ]]; then
  printf '%s\n' "$TEST_WORKTREE"
fi
EOF

  cat >"$TEST_BIN/roots" <<'EOF'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
set +x

while IFS= read -r _repository; do
  if [[ "$_repository" != "$TEST_REPOSITORY" ]]; then
    printf 'Error: root not found in %s\n' "$_repository" >&2
    continue
  fi
  printf '%s\n' "$_repository"
done
EOF

  cat >"$TEST_BIN/fzf" <<'EOF'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
set +x

while IFS= read -r _candidate; do
  [[ "$_candidate" == "$TEST_WORKTREE" ]] || continue
  printf '%s\n' "$_candidate"
  exit 0
done
exit 1
EOF

  chmod +x "$TEST_BIN/ghq" "$TEST_BIN/roots" "$TEST_BIN/fzf"
}

function run_repository_search() {
  local _ghq_includes_worktree="$1"

  run --separate-stderr env \
    GHQ_INCLUDES_WORKTREE="$_ghq_includes_worktree" \
    HOME="$TEST_HOME" \
    XDG_CACHE_HOME="$TEST_HOME/.cache" \
    FPATH="$TEST_FUNCTIONS" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfi -c \
    "source '$REPO_ROOT/zsh/.zshrc'; function zle() { :; }; ghq-fzf; print -r -- \"\$BUFFER\""
}
