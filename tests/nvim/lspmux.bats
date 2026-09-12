#!/usr/bin/env bats
# Executable specifications for Rust-only LSP multiplexing.

bats_require_minimum_version 1.5.0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

@test "Rust uses lspmux with a global analyzer and preserves clippy" {
  run env DOTFILES_ROOT="$REPO_ROOT" nvim --headless -u NONE -i NONE -l /dev/stdin <<'LUA'
local root = vim.env.DOTFILES_ROOT
dofile(root .. "/nvim/lua/plugins/lsp.lua")[1].config()
local config = vim.lsp.config.rust_analyzer
assert(type(config.cmd) == "table" and config.cmd[1] == "lspmux", "Rust must connect through lspmux")
assert(config.cmd[2] == "client")
assert(config.cmd[3] == "--server-path")
assert(config.cmd[4] == vim.fn.expand("~/.local/bin/rust-analyzer"))
assert(config.settings["rust-analyzer"].check.command == "clippy")
for _, name in ipairs({ "nixd", "bashls", "ruff", "ty", "ts_ls", "texlab", "ltex", "lua_ls" }) do
  local cmd = vim.lsp.config[name].cmd
  assert(type(cmd) ~= "table" or cmd[1] ~= "lspmux", name .. " must start directly")
end
LUA

  [ "$status" -eq 0 ]
}
