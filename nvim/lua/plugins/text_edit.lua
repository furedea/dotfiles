return {
  -- Cursor jump
  {
    "folke/flash.nvim",
    event = "VeryLazy",
    opts = {},
    keys = {
      {
        "<leader>s",
        mode = { "n", "x", "o" },
        function()
          require("flash").jump()
        end,
        desc = "Flash",
      },
      {
        "<leader>S",
        mode = { "n", "x", "o" },
        function()
          require("flash").treesitter()
        end,
        desc = "Flash Treesitter",
      },
    },
  },

  -- Auto pair completion
  {
    "windwp/nvim-autopairs",
    event = "InsertEnter",
    opts = {},
  },

  -- Search count display
  {
    "kevinhwang91/nvim-hlslens",
    event = "CmdlineEnter",
    opts = {},
  },

  -- Comment toggle
  {
    "numToStr/Comment.nvim",
    event = "VeryLazy",
    opts = {},
  },

  -- Fuzzy finder
  {
    "nvim-telescope/telescope.nvim",
    cmd = "Telescope",
    keys = {
      { "<leader>ff", "<cmd>Telescope find_files<cr>", desc = "Find files" },
      { "<leader>fg", "<cmd>Telescope live_grep<cr>", desc = "Live grep" },
      { "<leader>fb", "<cmd>Telescope buffers<cr>", desc = "Buffers" },
      { "<leader>fh", "<cmd>Telescope help_tags<cr>", desc = "Help tags" },
    },
    dependencies = {
      "nvim-lua/plenary.nvim",
      {
        "nvim-telescope/telescope-fzf-native.nvim",
        build = "make",
      },
    },
    config = function()
      require("telescope").setup({})
      require("telescope").load_extension("fzf")
    end,
  },

  -- Syntax highlighting
  {
    "nvim-treesitter/nvim-treesitter",
    event = { "BufReadPost", "BufNewFile" },
    build = ":TSUpdate",
    config = function()
      require("nvim-treesitter").install({
        "bash",
        "lua",
        "python",
        "javascript",
        "typescript",
        "json",
        "yaml",
        "markdown",
        "nix",
        "vim",
        "vimdoc",
      })
    end,
  },

  -- Auto close/rename HTML tags
  {
    "windwp/nvim-ts-autotag",
    event = "InsertEnter",
    dependencies = { "nvim-treesitter/nvim-treesitter" },
    opts = {},
  },

  -- Color picker and highlighter
  {
    "uga-rosa/ccc.nvim",
    event = "BufReadPost",
    config = function()
      require("ccc").setup({
        highlighter = {
          auto_enable = true,
        },
      })
    end,
  },

  -- Regex explainer
  {
    "bennypowers/nvim-regexplainer",
    cmd = "RegexplainerToggle",
    dependencies = {
      "nvim-treesitter/nvim-treesitter",
      "MunifTanjim/nui.nvim",
    },
    opts = {},
  },
}
