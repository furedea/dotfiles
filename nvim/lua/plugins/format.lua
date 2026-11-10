return {
  {
    "stevearc/conform.nvim",
    event = { "BufReadPre", "BufNewFile" },
    config = function()
      require("conform").setup({
        format_on_save = { timeout_ms = 1000, lsp_format = "fallback" },
        formatters = {
          -- Fall back to ~/dprint.json for files outside any dprint project (e.g. $TMPDIR)
          dprint = {
            args = function(_, ctx)
              local has_project_config = vim.fs.find(
                { "dprint.json", ".dprint.json", "dprint.jsonc", ".dprint.jsonc" },
                { upward = true, path = ctx.dirname }
              )[1]
              if has_project_config then
                return { "fmt", "--stdin", "$FILENAME" }
              end
              return { "fmt", "--config", vim.fn.expand("~/dprint.json"), "--stdin", "$FILENAME" }
            end,
          },
        },
        formatters_by_ft = {
          -- Text files: CJK spacing then structure formatting
          markdown = { "autocorrect", "dprint" },
          nix = { "nixfmt" },
          lua = { "stylua" },
          tex = { "tex-fmt" },
          plaintex = { "tex-fmt" },
          bib = { "tex-fmt" },
          text = { "autocorrect" },
          -- Programming languages: each ecosystem's de facto formatter
          sh = { "shfmt" },
          bash = { "shfmt" },
          python = { "ruff_format" },
          rust = { "rustfmt" },
          javascript = { "oxfmt" },
          javascriptreact = { "oxfmt" },
          typescript = { "oxfmt" },
          typescriptreact = { "oxfmt" },
          json = { "dprint" },
          toml = { "dprint" },
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
          -- tex buffers are handled via :update in tex.lua so latexmk recompiles
          local ft = vim.bo[bufnr].filetype
          if ft == "tex" or ft == "plaintex" then
            return
          end

          local tick = vim.api.nvim_buf_get_changedtick(bufnr)
          if last_tick[bufnr] == tick then
            return
          end
          last_tick[bufnr] = tick
          require("conform").format({ bufnr = bufnr, async = true })
        end,
      })
    end,
  },
}
