return {
  {
    "mfussenegger/nvim-lint",
    event = { "BufReadPost", "BufWritePost", "InsertLeave" },
    config = function()
      local lint = require("lint")
      lint.linters.chktex = vim.tbl_extend("force", lint.linters.chktex or {}, {
        ignore_exitcode = true,
      })
      lint.linters.oxlint = vim.tbl_extend("force", lint.linters.oxlint or {}, {
        cwd = function()
          return vim.fs.root(0, {
            ".oxlintrc.json",
            ".oxlintrc.jsonc",
            "package.json",
            "pnpm-lock.yaml",
            ".git",
          })
        end,
      })

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
          lint.try_lint()
        end,
      })
    end,
  },
}
