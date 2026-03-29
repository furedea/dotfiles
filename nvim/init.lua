vim.g.mapleader = " "
vim.g.maplocalleader = " "

vim.keymap.set("i", "jj", "<ESC>", { silent = true })

vim.opt.shiftwidth = 4
vim.opt.tabstop = 4
vim.opt.expandtab = true
vim.opt.textwidth = 0
vim.opt.autoindent = true
vim.opt.hlsearch = true
vim.opt.clipboard = "unnamedplus"
vim.opt.splitright = true
vim.opt.splitbelow = true

local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", -- latest stable release
    lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup("plugins")

-- Auto-restore session when opening nvim without arguments
vim.api.nvim_create_autocmd("VimEnter", {
  nested = true,
  callback = function()
    if vim.fn.argc() == 0 then
      require("persistence").load()
    end
  end,
})

vim.api.nvim_create_autocmd("BufReadPost", {
  pattern = { "*.json", "*.jsonl" },
  callback = function(args)
    if vim.fn.executable("jq") ~= 1 then
      return
    end

    if vim.bo[args.buf].modified or vim.bo[args.buf].buftype ~= "" then
      return
    end

    local view = vim.fn.winsaveview()
    local lines = vim.api.nvim_buf_get_lines(args.buf, 0, -1, false)
    local content = table.concat(lines, "\n")
    local formatted = vim.fn.system({ "jq", "." }, content)

    if vim.v.shell_error ~= 0 then
      return
    end

    local new_lines = vim.split(vim.trim(formatted), "\n", { plain = true })
    vim.api.nvim_buf_set_lines(args.buf, 0, -1, false, new_lines)
    vim.fn.winrestview(view)
    vim.bo[args.buf].modified = false
  end,
})
