#!/usr/bin/env bats
# Executable specifications for building Zsh startup caches.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$REPO_ROOT/zsh/build_cache.sh"
  TEST_ZSHRC="$BATS_TEST_TMPDIR/.zshrc"
  TEST_ZCOMPDUMP="$BATS_TEST_TMPDIR/cache/.zcompdump"
  ZSH_BIN="$(command -v zsh)"

  printf 'function cached_function() { :; }\n' >"$TEST_ZSHRC"
}

@test "builds a reusable completion dump" {
  run bash "$SCRIPT" "$ZSH_BIN" "$TEST_ZSHRC" "$TEST_ZCOMPDUMP"

  [ "$status" -eq 0 ]
  [ -s "$TEST_ZCOMPDUMP" ]
}

@test "compiles the completion dump to Zsh word code" {
  bash "$SCRIPT" "$ZSH_BIN" "$TEST_ZSHRC" "$TEST_ZCOMPDUMP"

  [ -s "$TEST_ZCOMPDUMP.zwc" ]
  "$ZSH_BIN" -fc 'zcompile -t "$1"' _ "$TEST_ZCOMPDUMP.zwc"
}

@test "compiles the startup file to Zsh word code" {
  bash "$SCRIPT" "$ZSH_BIN" "$TEST_ZSHRC" "$TEST_ZCOMPDUMP"

  [ -s "$TEST_ZSHRC.zwc" ]
  "$ZSH_BIN" -fc 'zcompile -t "$1"' _ "$TEST_ZSHRC.zwc"
}

@test "replaces a stale completion dump during cache rebuild" {
  bash "$SCRIPT" "$ZSH_BIN" "$TEST_ZSHRC" "$TEST_ZCOMPDUMP"
  printf 'ZSH_CACHE_SENTINEL=stale\n' >>"$TEST_ZCOMPDUMP"

  bash "$SCRIPT" "$ZSH_BIN" "$TEST_ZSHRC" "$TEST_ZCOMPDUMP"

  ! grep -q 'ZSH_CACHE_SENTINEL' "$TEST_ZCOMPDUMP"
}
