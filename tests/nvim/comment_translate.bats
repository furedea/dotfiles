#!/usr/bin/env bats
# Executable specifications for comment translation privacy.

bats_require_minimum_version 1.5.0

@test "comment translation never sends string literals to the translate service" {
  local REPO_ROOT
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  readonly REPO_ROOT

  run env DOTFILES_ROOT="$REPO_ROOT" nvim --headless -u NONE -i NONE -l /dev/stdin <<'LUA'
local root = vim.env.DOTFILES_ROOT
local specs = dofile(root .. "/nvim/lua/plugins/other.lua")
local opts
for _, spec in ipairs(specs) do
  if spec[1] == "noir4y/comment-translate.nvim" then
    opts = spec.opts
  end
end
assert(opts, "comment-translate.nvim must be configured")
assert(opts.targets.string == false, "string literals must not be translated")
assert(opts.targets.comment == true, "comments must stay translatable")
LUA

  [ "$status" -eq 0 ]
}
