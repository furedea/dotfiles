return {
  {
    "mfussenegger/nvim-lint",
    event = { "BufReadPost", "BufWritePost", "InsertLeave" },
    config = function()
      local lint = require("lint")

      lint.linters_by_ft = {
        nix = { "statix", "deadnix" },
        lua = { "selene" },
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
