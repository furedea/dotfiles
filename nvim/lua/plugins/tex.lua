return {
  {
    "lervag/vimtex",
    lazy = false,
    init = function()
      vim.g.vimtex_view_method = "skim"
      vim.g.vimtex_view_skim_sync = 1
      vim.g.vimtex_view_skim_activate = 1
      vim.g.vimtex_compiler_method = "latexmk"
      vim.g.vimtex_quickfix_mode = 2
      vim.g.vimtex_quickfix_open_on_warning = 0
      vim.g.vimtex_quickfix_autoclose_after_keystrokes = 2

      -- Write on InsertLeave so latexmk recompiles and Skim refreshes.
      -- :update is a no-op when the buffer is unchanged.
      local group = vim.api.nvim_create_augroup("tex_buffer_settings", { clear = true })
      vim.api.nvim_create_autocmd("FileType", {
        group = group,
        pattern = { "tex", "plaintex", "bib" },
        callback = function(args)
          vim.bo[args.buf].expandtab = true
          vim.bo[args.buf].shiftwidth = 2
          vim.bo[args.buf].softtabstop = 2
          vim.bo[args.buf].tabstop = 2

          local ft = vim.bo[args.buf].filetype
          if ft == "bib" then
            return
          end

          vim.api.nvim_create_autocmd("InsertLeave", {
            group = group,
            buffer = args.buf,
            callback = function()
              if vim.bo.modified then
                vim.cmd("silent update")
              end
            end,
          })
        end,
      })
    end,
  },
}
