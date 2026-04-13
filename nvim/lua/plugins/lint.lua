return {
  {
    "mfussenegger/nvim-lint",
    event = { "BufReadPost", "BufWritePost", "InsertLeave" },
    config = function()
      local lint = require("lint")
      lint.linters.chktex = vim.tbl_extend("force", lint.linters.chktex or {}, {
        ignore_exitcode = true,
      })

      local oxlint_filetypes = {
        javascript = true,
        javascriptreact = true,
        typescript = true,
        typescriptreact = true,
        vue = true,
        svelte = true,
        astro = true,
      }
      local oxlint_root_markers = {
        ".oxlintrc.json",
        ".oxlintrc.jsonc",
        "package.json",
        "pnpm-lock.yaml",
        ".git",
      }

      lint.linters_by_ft = {
        ghaction = { "actionlint" },
        nix = { "statix", "deadnix" },
        lua = { "selene" },
        sh = { "shellcheck" },
        bash = { "shellcheck" },
        javascript = { "oxlint" },
        javascriptreact = { "oxlint" },
        typescript = { "oxlint" },
        typescriptreact = { "oxlint" },
        vue = { "oxlint" },
        svelte = { "oxlint" },
        astro = { "oxlint" },
        tex = { "chktex" },
        plaintex = { "chktex" },
      }

      -- nvim-lint no-ops on filetypes missing from linters_by_ft, so a single
      -- autocmd covers all registered languages.
      local lint_group = vim.api.nvim_create_augroup("lint", { clear = true })
      vim.api.nvim_create_autocmd({ "BufEnter", "BufWritePost", "InsertLeave" }, {
        group = lint_group,
        callback = function(args)
          if vim.bo[args.buf].buftype ~= "" then
            return
          end

          local opts = nil
          if oxlint_filetypes[vim.bo[args.buf].filetype] then
            opts = {
              cwd = vim.fs.root(args.buf, oxlint_root_markers),
            }
          end

          lint.try_lint(nil, opts)
        end,
      })
    end,
  },
}
