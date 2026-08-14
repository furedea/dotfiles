local M = {}

local function realpath(file)
  return vim.uv.fs_realpath(file) or vim.fs.normalize(file)
end

local function save_error(result)
  local detail = vim.trim(result.stderr or "")
  return detail == "" and "Failed to save esa post as WIP"
    or "Failed to save esa post as WIP: " .. detail
end

function M.setup()
  local post_number = vim.env.ESA_EDIT_POST_NUMBER
  local file = vim.env.ESA_EDIT_FILE
  if not post_number or post_number == "" or not file or file == "" then
    return
  end

  local save_command = {
    "esa",
    "post",
    "update",
    post_number,
    "--body-file",
    file,
    "--wip",
    "--message",
    "[skip notice]",
  }
  local edit_file = realpath(file)
  local group = vim.api.nvim_create_augroup("esa_wip_on_save", { clear = true })
  vim.api.nvim_create_autocmd("BufWriteCmd", {
    group = group,
    pattern = vim.fn.fnameescape(edit_file),
    callback = function(args)
      local buffer_file = realpath(vim.api.nvim_buf_get_name(args.buf))
      if buffer_file ~= edit_file then
        return
      end

      vim.api.nvim_buf_call(args.buf, function()
        vim.cmd("silent noautocmd write")
      end)
      local result = vim.system(save_command, { text = true }):wait()
      if result.code ~= 0 then
        vim.bo[args.buf].modified = true
        error(save_error(result), 0)
      end
    end,
  })
end

return M
