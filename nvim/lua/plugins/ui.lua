return {
  -- Color scheme
  {
    "catppuccin/nvim",
    name = "catppuccin",
    lazy = false,
    priority = 1000,
    opts = {
      flavour = "mocha",
    },
    config = function(_, opts)
      require("catppuccin").setup(opts)
      vim.cmd.colorscheme("catppuccin")
    end,
  },

  -- Buffer tabs
  {
    "romgrk/barbar.nvim",
    event = "BufReadPre",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      animation = false,
    },
    keys = {
      { "<C-,>", "<cmd>BufferPrevious<cr>", desc = "Previous buffer" },
      { "<C-.>", "<cmd>BufferNext<cr>", desc = "Next buffer" },
      { "<C-1>", "<cmd>BufferGoto 1<cr>", desc = "Buffer 1" },
      { "<C-2>", "<cmd>BufferGoto 2<cr>", desc = "Buffer 2" },
      { "<C-3>", "<cmd>BufferGoto 3<cr>", desc = "Buffer 3" },
      { "<C-4>", "<cmd>BufferGoto 4<cr>", desc = "Buffer 4" },
      { "<C-5>", "<cmd>BufferGoto 5<cr>", desc = "Buffer 5" },
      { "<C-6>", "<cmd>BufferGoto 6<cr>", desc = "Buffer 6" },
      { "<C-7>", "<cmd>BufferGoto 7<cr>", desc = "Buffer 7" },
      { "<C-8>", "<cmd>BufferGoto 8<cr>", desc = "Buffer 8" },
      { "<C-9>", "<cmd>BufferGoto 9<cr>", desc = "Buffer 9" },
      { "<C-0>", "<cmd>BufferLast<cr>", desc = "Last buffer" },
      { "<C-c>", "<cmd>BufferClose<cr>", desc = "Close buffer" },
    },
  },

  -- Statusline
  {
    "nvim-lualine/lualine.nvim",
    event = "VeryLazy",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      options = {
        theme = "catppuccin",
      },
    },
  },

  -- UI replacement for cmdline, messages, notifications
  {
    "folke/noice.nvim",
    event = "VeryLazy",
    dependencies = {
      "MunifTanjim/nui.nvim",
    },
    opts = {
      lsp = {
        override = {
          ["vim.lsp.util.convert_input_to_markdown_lines"] = true,
          ["vim.lsp.util.stylize_markdown"] = true,
        },
      },
      presets = {
        bottom_search = true,
        command_palette = true,
        long_message_to_split = true,
      },
    },
  },

  -- Mode-based line highlighting
  {
    "mvllow/modes.nvim",
    event = "VeryLazy",
    opts = {
      line_opacity = 0.15,
    },
  },

  -- Indent guides and chunk highlighting
  {
    "shellRaining/hlchunk.nvim",
    event = { "BufReadPre", "BufNewFile" },
    opts = {
      chunk = { enable = true },
      indent = { enable = true },
    },
  },

  -- Rainbow bracket coloring
  {
    "HiPhish/rainbow-delimiters.nvim",
    event = "BufReadPost",
    config = function()
      require("rainbow-delimiters.setup").setup({})
    end,
  },

  -- Highlight changed text on undo/redo
  {
    "tzachar/highlight-undo.nvim",
    event = "VeryLazy",
    opts = {},
  },

  -- Rich markdown rendering
  {
    "MeanderingProgrammer/render-markdown.nvim",
    ft = "markdown",
    dependencies = {
      "nvim-treesitter/nvim-treesitter",
      "nvim-tree/nvim-web-devicons",
    },
    opts = {},
  },

  -- File tree as buffer
  {
    "stevearc/oil.nvim",
    cmd = "Oil",
    keys = {
      { "<leader>e", "<cmd>Oil<cr>", desc = "Open file explorer" },
    },
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {
      preview_win = {
        update_on_cursor_moved = true,
      },
    },
    config = function(_, opts)
      require("oil").setup(opts)
      -- Auto-open preview and shrink oil window
      vim.api.nvim_create_autocmd("User", {
        pattern = "OilEnter",
        callback = vim.schedule_wrap(function(args)
          local oil = require("oil")
          if vim.api.nvim_get_current_buf() == args.data.buf and oil.get_cursor_entry() then
            local oil_win = vim.api.nvim_get_current_win()
            oil.open_preview({}, function()
              local oil_width = math.floor(vim.o.columns * 0.1)
              vim.api.nvim_win_set_width(oil_win, oil_width)
            end)
          end
        end),
      })
    end,
  },
}
