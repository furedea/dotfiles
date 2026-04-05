return {
  {
    "mfussenegger/nvim-lint",
    event = { "BufReadPost", "BufWritePost", "InsertLeave" },
    config = function()
      local lint = require("lint")

      lint.linters_by_ft = {
        nix = { "statix", "deadnix" },
      }

      local lint_group = vim.api.nvim_create_augroup("nix-lint", { clear = true })
      vim.api.nvim_create_autocmd({ "BufEnter", "BufWritePost", "InsertLeave" }, {
        group = lint_group,
        callback = function(args)
          if vim.bo[args.buf].buftype ~= "" then
            return
          end

          if vim.bo[args.buf].filetype ~= "nix" then
            return
          end

          lint.try_lint()
        end,
      })
    end,
  },
}
