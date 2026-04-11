return {
  -- LSP server management
  {
    "neovim/nvim-lspconfig",
    event = { "BufReadPre", "BufNewFile" },
    config = function()
      local function find_workspace_binary(root_dir, binary_name)
        if not root_dir then
          return binary_name
        end

        local local_binary = vim.fs.joinpath(root_dir, "node_modules", ".bin", binary_name)
        if vim.fn.executable(local_binary) == 1 then
          return local_binary
        end

        return binary_name
      end

      vim.lsp.config("nixd", {})
      vim.lsp.config("bashls", {})
      vim.lsp.config("ruff", {})
      vim.lsp.config("ty", {})
      vim.lsp.config("ts_ls", {
        init_options = { hostInfo = "neovim" },
        cmd = function(dispatchers, config)
          local command = find_workspace_binary(config.root_dir, "typescript-language-server")
          return vim.lsp.rpc.start({ command, "--stdio" }, dispatchers)
        end,
      })
      vim.lsp.config("texlab", {})
      vim.lsp.config("ltex", {
        cmd = { "ltex-ls" },
        filetypes = { "tex", "plaintex", "bib" },
        root_markers = { ".git" },
        settings = {
          ltex = {
            checkFrequency = "save",
            language = "en-US",
          },
        },
      })
      vim.lsp.config("rust_analyzer", {
        settings = {
          ["rust-analyzer"] = {
            check = {
              command = "clippy",
            },
          },
        },
      })
      vim.lsp.config("lua_ls", {
        settings = {
          Lua = {
            runtime = { version = "LuaJIT" },
            diagnostics = { globals = { "vim" } },
            workspace = {
              library = vim.api.nvim_get_runtime_file("", true),
              checkThirdParty = false,
            },
            telemetry = { enable = false },
          },
        },
      })
      vim.lsp.enable("nixd")
      vim.lsp.enable("bashls")
      vim.lsp.enable("ruff")
      vim.lsp.enable("ty")
      vim.lsp.enable("ts_ls")
      vim.lsp.enable("texlab")
      vim.lsp.enable("ltex")
      vim.lsp.enable("rust_analyzer")
      vim.lsp.enable("lua_ls")

      -- Auto-show diagnostics/hover on CursorHold (toggleable)
      vim.g.auto_hover = true
      vim.o.updatetime = 500
      vim.keymap.set("n", "<leader>th", function()
        vim.g.auto_hover = not vim.g.auto_hover
        vim.notify("Auto hover: " .. (vim.g.auto_hover and "ON" or "OFF"))
      end, { desc = "Toggle auto hover" })
      vim.api.nvim_create_autocmd("CursorHold", {
        callback = function()
          if not vim.g.auto_hover then
            return
          end
          local diagnostics =
            vim.diagnostic.get(0, { lnum = vim.api.nvim_win_get_cursor(0)[1] - 1 })
          if #diagnostics > 0 then
            vim.diagnostic.open_float({ focusable = false })
          end
          vim.schedule(function()
            local clients = vim.lsp.get_clients({ bufnr = 0 })
            if #clients > 0 then
              vim.lsp.buf.hover()
            end
          end)
        end,
      })

      vim.api.nvim_create_autocmd("LspAttach", {
        callback = function(ev)
          local opts = { buffer = ev.buf }
          vim.keymap.set("n", "K", vim.lsp.buf.hover, opts)
          vim.keymap.set(
            "n",
            "<leader>rn",
            ":IncRename ",
            vim.tbl_extend("force", opts, { desc = "Incremental rename" })
          )
          vim.keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, opts)
        end,
      })
    end,
  },

  -- Peek references without page jump
  {
    "nvimdev/lspsaga.nvim",
    event = "LspAttach",
    dependencies = {
      "nvim-treesitter/nvim-treesitter",
      "nvim-tree/nvim-web-devicons",
    },
    opts = {
      finder = {
        keys = {
          toggle_or_open = "<CR>",
        },
      },
    },
    keys = {
      { "gd", "<cmd>Lspsaga peek_definition<cr>", desc = "Peek definition" },
      { "gr", "<cmd>Lspsaga finder<cr>", desc = "Find references" },
    },
  },

  -- LSP error display
  {
    "folke/trouble.nvim",
    cmd = "Trouble",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    opts = {},
    keys = {
      { "<leader>xx", "<cmd>Trouble diagnostics toggle<cr>", desc = "Diagnostics" },
      {
        "<leader>xd",
        "<cmd>Trouble diagnostics toggle filter.buf=0<cr>",
        desc = "Buffer diagnostics",
      },
    },
  },

  -- Incremental rename with live preview
  {
    "smjonas/inc-rename.nvim",
    cmd = "IncRename",
    opts = {},
  },

  -- Dim unused variables/functions
  {
    "zbirenbaum/neodim",
    event = "LspAttach",
    opts = {
      alpha = 0.75,
      hide = {
        underline = true,
        virtual_text = true,
        signs = true,
      },
    },
  },

  -- Show definition while scrolling
  {
    "nvim-treesitter/nvim-treesitter-context",
    event = "BufReadPost",
    dependencies = { "nvim-treesitter/nvim-treesitter" },
    opts = {
      max_lines = 3,
    },
  },
}
