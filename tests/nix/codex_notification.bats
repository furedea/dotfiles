#!/usr/bin/env bats
# Codex delegates terminal notifications only when launched inside Herdr.
# Bats isolates each test's environment.
# shellcheck disable=SC2030,SC2031

setup_file() {
  local _repo_root _derivation _package
  _repo_root="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  _derivation=$(nix eval --raw \
    "$_repo_root#homeConfigurations.kaito.config.home.packages" \
    --apply 'packages: (builtins.head (builtins.filter (p: p.name == "codex") packages)).drvPath')
  _package=$(nix build --no-link --print-out-paths "$_derivation^*")
  export CODEX_WRAPPER="$_package/bin/codex"
}

capture_codex_arguments() {
  # Intercept the generated wrapper's exec without starting a real agent.
  # shellcheck disable=SC2329
  exec() {
    shift 3
    printf '%s\n' "$@"
  }
  # shellcheck source=/dev/null
  source "$CODEX_WRAPPER" "$@"
}

@test "Codex retains native notifications outside Herdr" {
  unset HERDR_ENV
  run capture_codex_arguments resume --last "a prompt with spaces"
  [ "$status" -eq 0 ]
  [ "$output" = $'resume\n--last\na prompt with spaces' ]
}

@test "Codex delegates notifications inside Herdr without changing user arguments" {
  export HERDR_ENV=1
  run capture_codex_arguments resume --last "a prompt with spaces"
  [ "$status" -eq 0 ]
  [ "$output" = $'-c\ntui.notifications=false\nresume\n--last\na prompt with spaces' ]
}

@test "a disabled Herdr environment retains native notifications" {
  export HERDR_ENV=0
  run capture_codex_arguments --version
  [ "$status" -eq 0 ]
  [ "$output" = '--version' ]
}
