#!/usr/bin/env bats
# Executable specifications for Neovim plugins that must not fetch code at runtime.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "blink.cmp builds its matcher locally instead of downloading a binary" {
  run env DOTFILES_ROOT="$REPO_ROOT" nvim --headless -u NONE -i NONE -l /dev/stdin <<'LUA'
local root = vim.env.DOTFILES_ROOT
local spec
for _, plugin in ipairs(dofile(root .. "/nvim/lua/plugins/completion.lua")) do
  if plugin[1] == "saghen/blink.cmp" then spec = plugin end
end
assert(spec, "blink.cmp spec is missing")
assert(spec.opts.fuzzy.prebuilt_binaries.download == false, "prebuilt download must be disabled")
assert(spec.build == "cargo build --release", "the matcher must be built from the locked checkout")
LUA

  [ "$status" -eq 0 ]
}

@test "nvim-regexplainer never installs Python packages on its own" {
  run env DOTFILES_ROOT="$REPO_ROOT" nvim --headless -u NONE -i NONE -l /dev/stdin <<'LUA'
local root = vim.env.DOTFILES_ROOT
local spec
for _, plugin in ipairs(dofile(root .. "/nvim/lua/plugins/text_edit.lua")) do
  if plugin[1] == "bennypowers/nvim-regexplainer" then spec = plugin end
end
assert(spec, "nvim-regexplainer spec is missing")
assert(spec.opts.deps.auto_install == false, "auto_install must be disabled")
LUA

  [ "$status" -eq 0 ]
}
