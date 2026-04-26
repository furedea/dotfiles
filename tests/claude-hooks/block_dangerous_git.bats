#!/usr/bin/env bats
# Tests for .claude/hooks/block_dangerous_git.sh

setup() {
  load test_helper/setup
  HOOK="$HOOK_DIR/block_dangerous_git.sh"
}

# --- Allowed: normal pushes ---

@test "allows push to feature branch" {
  run bash "$HOOK" <<< "$(make_input 'git push origin feature/foo')"
  [ "$status" -eq 0 ]
}

@test "allows -u origin feature/foo (boolean -u, does not consume origin)" {
  run bash "$HOOK" <<< "$(make_input 'git push -u origin feature/foo')"
  [ "$status" -eq 0 ]
}

@test "allows --set-upstream origin feature/bar (boolean --set-upstream)" {
  run bash "$HOOK" <<< "$(make_input 'git push --set-upstream origin feature/bar')"
  [ "$status" -eq 0 ]
}

@test "allows bare git push from feature branch" {
  create_temp_git_repo
  git -C "$TEMP_REPO" checkout -b feature/bar --quiet
  (
    cd "$TEMP_REPO"
    run bash "$HOOK" <<< "$(make_input 'git push')"
    [ "$status" -eq 0 ]
  )
}

@test "allows git pull (not governed)" {
  run bash "$HOOK" <<< "$(make_input 'git pull origin main')"
  [ "$status" -eq 0 ]
}

# --- Allowed: merges and passthrough ---

@test "allows gh pr merge without --admin" {
  run bash "$HOOK" <<< "$(make_input 'gh pr merge 42 --squash')"
  [ "$status" -eq 0 ]
}

@test "allows gh pr merge with rebase" {
  run bash "$HOOK" <<< "$(make_input 'gh pr merge 42 --rebase')"
  [ "$status" -eq 0 ]
}

@test "passes through ls" {
  run bash "$HOOK" <<< "$(make_input 'ls -la')"
  [ "$status" -eq 0 ]
}

@test "passes through git status" {
  run bash "$HOOK" <<< "$(make_input 'git status')"
  [ "$status" -eq 0 ]
}

@test "passes through empty command" {
  run bash "$HOOK" <<< '{"tool_input":{"command":""}}'
  [ "$status" -eq 0 ]
}

# --- Blocked: force push flags ---

@test "blocks --force" {
  run bash "$HOOK" <<< "$(make_input 'git push --force origin feature/foo')"
  [ "$status" -eq 2 ]
  [[ "$output" == *"force-push flag"* ]]
}

@test "blocks -f short flag" {
  run bash "$HOOK" <<< "$(make_input 'git push -f origin feature/foo')"
  [ "$status" -eq 2 ]
}

@test "blocks --force-with-lease" {
  run bash "$HOOK" <<< "$(make_input 'git push --force-with-lease origin feature/foo')"
  [ "$status" -eq 2 ]
}

@test "blocks --force-with-lease with value" {
  run bash "$HOOK" <<< "$(make_input 'git push --force-with-lease=origin/foo origin feature/foo')"
  [ "$status" -eq 2 ]
}

# --- Blocked: +refspec force ---

@test "blocks +refspec" {
  run bash "$HOOK" <<< "$(make_input 'git push origin +feature/foo')"
  [ "$status" -eq 2 ]
  [[ "$output" == *"refspec"* ]]
}

@test "blocks +src:dst refspec" {
  run bash "$HOOK" <<< "$(make_input 'git push origin +feature/foo:main')"
  [ "$status" -eq 2 ]
}

# --- Blocked: explicit push to main/master ---

@test "blocks explicit origin main" {
  run bash "$HOOK" <<< "$(make_input 'git push origin main')"
  [ "$status" -eq 2 ]
  [[ "$output" == *"main"* ]]
}

@test "blocks explicit origin master" {
  run bash "$HOOK" <<< "$(make_input 'git push origin master')"
  [ "$status" -eq 2 ]
  [[ "$output" == *"master"* ]]
}

@test "blocks HEAD:main refspec" {
  run bash "$HOOK" <<< "$(make_input 'git push origin HEAD:main')"
  [ "$status" -eq 2 ]
}

@test "blocks src:main refspec" {
  run bash "$HOOK" <<< "$(make_input 'git push origin feature/foo:main')"
  [ "$status" -eq 2 ]
}

@test "blocks multi-refspec with main included" {
  run bash "$HOOK" <<< "$(make_input 'git push -u origin feature/foo main')"
  [ "$status" -eq 2 ]
}

# --- Blocked: implicit push when current branch is main ---

@test "blocks implicit push from main" {
  create_temp_git_repo
  # Normalize the initial branch to 'main' regardless of git default.
  git -C "$TEMP_REPO" branch -M main
  (
    cd "$TEMP_REPO"
    run bash "$HOOK" <<< "$(make_input 'git push')"
    [ "$status" -eq 2 ]
    [[ "$output" == *"main"* ]]
  )
}

@test "allows implicit push from feature branch" {
  create_temp_git_repo
  git -C "$TEMP_REPO" checkout -b feature/foo --quiet
  (
    cd "$TEMP_REPO"
    run bash "$HOOK" <<< "$(make_input 'git push')"
    [ "$status" -eq 0 ]
  )
}

# --- Blocked: gh pr merge --admin ---

@test "blocks gh pr merge --admin (trailing)" {
  run bash "$HOOK" <<< "$(make_input 'gh pr merge 42 --admin')"
  [ "$status" -eq 2 ]
  [[ "$output" == *"admin"* ]]
}

@test "blocks gh pr merge with --admin in middle" {
  run bash "$HOOK" <<< "$(make_input 'gh pr merge --admin 42')"
  [ "$status" -eq 2 ]
}

# --- Blocked: compound-command bypass ---

@test "blocks push to main after cd (&&)" {
  run bash "$HOOK" <<< "$(make_input 'cd /tmp && git push origin main')"
  [ "$status" -eq 2 ]
}

@test "blocks --force in piped segment" {
  run bash "$HOOK" <<< "$(make_input 'foo | git push --force origin feature/foo')"
  [ "$status" -eq 2 ]
}

@test "blocks push to main after semicolon" {
  run bash "$HOOK" <<< "$(make_input 'git status; git push origin main')"
  [ "$status" -eq 2 ]
}

@test "allows pipe with no destructive segment" {
  run bash "$HOOK" <<< "$(make_input 'ls | cat')"
  [ "$status" -eq 0 ]
}

# --- Blocked: shell wrappers carrying destructive tokens ---

@test "blocks bash -c with --force" {
  run bash "$HOOK" <<< "$(make_input 'bash -c "git push --force origin main"')"
  [ "$status" -eq 2 ]
  [[ "$output" == *"wrapper"* ]]
}

@test "blocks sh -c with main push" {
  run bash "$HOOK" <<< "$(make_input 'sh -c "git push origin main"')"
  [ "$status" -eq 2 ]
}

@test "blocks /bin/bash -c with --force" {
  run bash "$HOOK" <<< "$(make_input '/bin/bash -c "git push --force"')"
  [ "$status" -eq 2 ]
}

@test "blocks eval with --force" {
  run bash "$HOOK" <<< "$(make_input 'eval "git push --force origin main"')"
  [ "$status" -eq 2 ]
}

@test "blocks zsh -c with admin merge" {
  run bash "$HOOK" <<< "$(make_input 'zsh -c "gh pr merge 42 --admin"')"
  [ "$status" -eq 2 ]
}

# --- Allowed: shell wrappers with benign content ---

@test "allows bash -c with ls" {
  run bash "$HOOK" <<< "$(make_input 'bash -c "ls -la"')"
  [ "$status" -eq 0 ]
}

@test "allows bash -c with echo" {
  run bash "$HOOK" <<< '{"tool_input":{"command":"bash -c \"echo hello\""}}'
  [ "$status" -eq 0 ]
}

# --- Blocked messages carry segment context ---

@test "blocked force-push message includes the offending segment" {
  run bash "$HOOK" <<< "$(make_input 'git push --force origin feature/foo')"
  [ "$status" -eq 2 ]
  [[ "$output" == *"Segment:"* ]]
  [[ "$output" == *"git push --force origin feature/foo"* ]]
}
