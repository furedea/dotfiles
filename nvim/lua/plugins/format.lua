return {
  {
    "stevearc/conform.nvim",
    event = { "BufReadPre", "BufNewFile" },
    config = function()
      require("conform").setup({
        formatters = {
          -- Use PRETTIERD_DEFAULT_CONFIG so prettierd finds ~/.prettierrc for files outside ~
          prettierd = {
            env = { PRETTIERD_DEFAULT_CONFIG = vim.fn.expand("~/.prettierrc") },
          },
        },
        formatters_by_ft = {
          -- Text files: CJK spacing then structure formatting
          markdown = { "autocorrect", "prettierd" },
          nix      = { "nixfmt" },
          text     = { "autocorrect" },
          -- Programming languages: each ecosystem's de facto formatter
          python   = { "ruff_format" },
          rust     = { "rustfmt" },
          json     = { "dprint" },
          toml     = { "dprint" },
        },
      })

      -- Format on InsertLeave, skip if buffer unchanged
      local last_tick = {}
      vim.api.nvim_create_autocmd("InsertLeave", {
        callback = function(args)
          local bufnr = args.buf
          if not vim.api.nvim_buf_is_valid(bufnr) or not vim.bo[bufnr].modifiable then
            return
          end

          local tick = vim.api.nvim_buf_get_changedtick(bufnr)
          if last_tick[bufnr] == tick then return end
          last_tick[bufnr] = tick
          require("conform").format({ bufnr = bufnr, async = true })
        end,
      })
    end,
  },
}
