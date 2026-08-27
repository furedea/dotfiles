#!/usr/bin/env bats
# Executable specifications for Zsh repository search behavior.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TEST_ROOT="$(cd "$BATS_TEST_TMPDIR" && pwd -P)"
  TEST_HOME="$TEST_ROOT/home"
  TEST_BIN="$TEST_ROOT/bin"
  TEST_REPOSITORY="$TEST_ROOT/ghq/github.com/example/repository"
  TEST_WORKTREE="$TEST_ROOT/worktrees/repository-feature"

  setup_zsh_startup_stubs
  setup_repository_search_fixture

  export REPO_ROOT
  export TEST_REPOSITORY
  export TEST_WORKTREE
}

function setup_zsh_startup_stubs() {
  mkdir -p \
    "$TEST_HOME/.config/zsh" \
    "$TEST_HOME/ghq/github.com/furedea/dotfiles/zsh" \
    "$TEST_BIN" \
    "$TEST_ROOT/functions"

  cat >"$TEST_ROOT/functions/compinit" <<'EOF'
function compinit() { :; }
EOF
  cat >"$TEST_HOME/.config/zsh/nix-plugins.zsh" <<'EOF'
function abbr() { :; }
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
    FPATH="$TEST_ROOT/functions" \
    PATH="$TEST_BIN:$PATH" \
    zsh -dfi -c \
    "source '$REPO_ROOT/zsh/.zshrc'; function zle() { :; }; ghq-fzf; print -r -- \"\$BUFFER\""
}

@test "repository search includes a registered worktree outside the ghq root" {
  run_repository_search false

  [ "$status" -eq 0 ]
  [ "$output" = "builtin cd $TEST_WORKTREE" ]
  [[ "$stderr" != *"root not found"* ]]
}

@test "repository search avoids roots errors for ghq-listed worktrees" {
  run_repository_search true

  [ "$status" -eq 0 ]
  [ "$output" = "builtin cd $TEST_WORKTREE" ]
  [[ "$stderr" != *"root not found"* ]]
}
