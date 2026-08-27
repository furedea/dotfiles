# Fixtures for Zsh repository search tests.

function setup_zsh_test_environment() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TEST_ROOT="$(cd "$BATS_TEST_TMPDIR" && pwd -P)"
  TEST_HOME="$TEST_ROOT/home"
  TEST_BIN="$TEST_ROOT/bin"
  TEST_FUNCTIONS="$TEST_ROOT/functions"
  COMPINIT_LOG="$TEST_ROOT/compinit.log"
  ABBR_LOG="$TEST_ROOT/abbr.log"

  create_zsh_startup_stubs

  export ABBR_LOG
  export COMPINIT_LOG
  export REPO_ROOT
  export TEST_BIN
  export TEST_FUNCTIONS
  export TEST_HOME
}

function create_zsh_startup_stubs() {
  mkdir -p \
    "$TEST_HOME/.config/zsh" \
    "$TEST_HOME/ghq/github.com/furedea/dotfiles/zsh" \
    "$TEST_BIN" \
    "$TEST_FUNCTIONS"

  cat >"$TEST_FUNCTIONS/compinit" <<'EOF'
print -r -- "$*" >>"$COMPINIT_LOG"
EOF
  cat >"$TEST_HOME/.config/zsh/nix-plugins.zsh" <<'EOF'
function abbr() { print -r -- "$*" >>"$ABBR_LOG"; }
EOF
  : >"$TEST_HOME/ghq/github.com/furedea/dotfiles/zsh/esa.zsh"

  local _command
  for _command in atuin carapace direnv starship zoxide; do
    cat >"$TEST_BIN/$_command" <<'EOF'
#!/bin/bash
set -euxCo pipefail
cd "$(dirname "$0")"
set +x
EOF
    chmod +x "$TEST_BIN/$_command"
  done
}

function setup_repository_search_fixture() {
  local _fixture_root
  _fixture_root="$(cd "$BATS_FILE_TMPDIR" && pwd -P)"
  TEST_REPOSITORY="$_fixture_root/ghq/github.com/example/repository"
  TEST_WORKTREE="$_fixture_root/ghq/github.com/example/repository-feature"
  TEST_EXTERNAL_WORKTREE="$_fixture_root/worktrees/repository-external"

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
  git -C "$TEST_REPOSITORY" worktree add --quiet \
    -b external "$TEST_EXTERNAL_WORKTREE"
  git -C "$TEST_REPOSITORY" worktree add --quiet -b feature "$TEST_WORKTREE"

  export TEST_EXTERNAL_WORKTREE
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
printf '%s\n' "$TEST_WORKTREE"
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

_selected=""
while IFS= read -r _candidate; do
  if [[ "$_candidate" == "$TEST_EXTERNAL_WORKTREE" ]]; then
    printf 'Unexpected worktree candidate: %s\n' "$_candidate" >&2
    exit 1
  fi
  if [[ "$_candidate" == "$TEST_WORKTREE" ]]; then
    _selected="$_candidate"
  fi
done
[[ -n "$_selected" ]]
printf '%s\n' "$_selected"
EOF

  chmod +x "$TEST_BIN/ghq" "$TEST_BIN/roots" "$TEST_BIN/fzf"
}

function run_repository_search() {
  run --separate-stderr env \
    HOME="$TEST_HOME" \
    XDG_CACHE_HOME="$TEST_HOME/.cache" \
    FPATH="$TEST_FUNCTIONS" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfi -c \
    "source '$REPO_ROOT/zsh/.zshrc'; function zle() { :; }; ghq-fzf; print -r -- \"\$BUFFER\""
}
