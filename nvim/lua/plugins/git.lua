return {
  -- Git operations in buffer
  {
    "lewis6991/gitsigns.nvim",
    event = { "BufReadPre", "BufNewFile" },
    opts = {
      on_attach = function(bufnr)
        local gs = require("gitsigns")
        local opts = { buffer = bufnr }

        vim.keymap.set("n", "]c", function()
          if vim.wo.diff then
            return "]c"
          end
          vim.schedule(function()
            gs.next_hunk()
          end)
          return "<Ignore>"
        end, vim.tbl_extend("force", opts, { expr = true, desc = "Next hunk" }))

        vim.keymap.set("n", "[c", function()
          if vim.wo.diff then
            return "[c"
          end
          vim.schedule(function()
            gs.prev_hunk()
          end)
          return "<Ignore>"
        end, vim.tbl_extend("force", opts, { expr = true, desc = "Previous hunk" }))

        -- stage/reset are disabled for jj compatibility (use jj commands instead)

        vim.keymap.set(
          "n",
          "<leader>hp",
          gs.preview_hunk,
          vim.tbl_extend("force", opts, { desc = "Preview hunk" })
        )
        vim.keymap.set("n", "<leader>hb", function()
          gs.blame_line({ full = true })
        end, vim.tbl_extend("force", opts, { desc = "Blame line" }))
      end,
    },
  },

  -- Conflict resolution
  {
    "akinsho/git-conflict.nvim",
    version = "*",
    event = "BufReadPost",
    opts = {},
  },

  -- Diff visualization
  {
    "sindrets/diffview.nvim",
    cmd = { "DiffviewOpen", "DiffviewFileHistory" },
    keys = {
      { "<leader>dv", "<cmd>DiffviewOpen<cr>", desc = "Open diffview" },
      { "<leader>dh", "<cmd>DiffviewFileHistory<cr>", desc = "File history" },
    },
    opts = {},
  },
}
