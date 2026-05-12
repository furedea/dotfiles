_:
let
  claudeHook = command: {
    inherit command;
    type = "command";
  };
  claudeHookIf = command: condition: (claudeHook command) // { "if" = condition; };
  codexHook = command: statusMessage: timeout: {
    inherit command statusMessage timeout;
    type = "command";
  };

  shellMatcher = "^(Bash|exec_command|functions\\.exec_command)$";
  editMatcher = "^apply_patch$|^Edit$|^Write$";
in
{
  claudeHooks = {
    UserPromptSubmit = [
      {
        matcher = "";
        hooks = [ (claudeHook "$HOME/.claude/hooks/guard_secret_content.sh prompt") ];
      }
    ];

    PreToolUse = [
      {
        matcher = "Bash";
        hooks = [
          (claudeHook "$HOME/.claude/hooks/audit_tool_call.sh")
          (claudeHook "$HOME/.claude/hooks/guard_forbidden_commands.sh")
          (claudeHook "$HOME/.claude/hooks/guard_secret_commit.sh")
          (claudeHook "$HOME/.claude/hooks/guard_dangerous_git.sh")
          (claudeHook "$HOME/.claude/hooks/guard_allowed_commands.sh")
        ];
      }
      {
        matcher = "Read";
        hooks = [
          (claudeHook "$HOME/.claude/hooks/audit_tool_call.sh")
          (claudeHook "$HOME/.claude/hooks/guard_secret_content.sh read")
        ];
      }
      {
        matcher = "Write|Edit|MultiEdit";
        hooks = [
          (claudeHook "$HOME/.claude/hooks/audit_tool_call.sh")
          (claudeHook "$HOME/.claude/hooks/guard_harness_files.sh")
          (claudeHook "$HOME/.claude/hooks/guard_secret_content.sh write")
        ];
      }
    ];

    PostToolUse = [
      {
        matcher = "Write|Edit|MultiEdit";
        hooks = [
          (claudeHookIf "$HOME/.claude/hooks/lint_format_py.sh" "Write(*.py)|Edit(*.py)|MultiEdit(*.py)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_sh.sh" "Write(*.sh)|Edit(*.sh)|MultiEdit(*.sh)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_js.sh" "Write(*.js)|Edit(*.js)|MultiEdit(*.js)|Write(*.ts)|Edit(*.ts)|MultiEdit(*.ts)|Write(*.jsx)|Edit(*.jsx)|MultiEdit(*.jsx)|Write(*.tsx)|Edit(*.tsx)|MultiEdit(*.tsx)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_rs.sh" "Write(*.rs)|Edit(*.rs)|MultiEdit(*.rs)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_nix.sh" "Write(*.nix)|Edit(*.nix)|MultiEdit(*.nix)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_md.sh" "Write(*.md)|Edit(*.md)|MultiEdit(*.md)|Write(*.markdown)|Edit(*.markdown)|MultiEdit(*.markdown)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_json_toml.sh" "Write(*.json)|Edit(*.json)|MultiEdit(*.json)|Write(*.toml)|Edit(*.toml)|MultiEdit(*.toml)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_gha.sh" "Write(*.yml)|Edit(*.yml)|MultiEdit(*.yml)|Write(*.yaml)|Edit(*.yaml)|MultiEdit(*.yaml)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_txt.sh" "Write(*.txt)|Edit(*.txt)|MultiEdit(*.txt)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_lua.sh" "Write(*.lua)|Edit(*.lua)|MultiEdit(*.lua)")
          (claudeHookIf "$HOME/.claude/hooks/lint_format_tex.sh" "Write(*.tex)|Edit(*.tex)|MultiEdit(*.tex)|Write(*.bib)|Edit(*.bib)|MultiEdit(*.bib)|Write(*.cls)|Edit(*.cls)|MultiEdit(*.cls)|Write(*.sty)|Edit(*.sty)|MultiEdit(*.sty)")
        ];
      }
      {
        matcher = "Bash|Edit|MultiEdit|Write|WebFetch|WebSearch|Task|Agent";
        hooks = [ (claudeHook "$HOME/.claude/hooks/audit_tool_call.sh") ];
      }
    ];

    Stop = [
      {
        matcher = "";
        hooks = [
          (claudeHook "$HOME/.claude/hooks/run_related_tests.sh")
          (claudeHook "$HOME/.claude/hooks/notify_macos_done.sh")
        ];
      }
    ];

    SubagentStop = [
      {
        matcher = "";
        hooks = [ (claudeHook "$HOME/.claude/hooks/notify_macos_done.sh") ];
      }
    ];

    Notification = [
      {
        matcher = "";
        hooks = [ (claudeHook "$HOME/.claude/hooks/notify_macos_await.sh") ];
      }
    ];

    PermissionDenied = [
      {
        hooks = [ (claudeHook "$HOME/.claude/hooks/audit_permission_denied.sh") ];
      }
    ];

    PreCompact = [
      {
        matcher = "";
        hooks = [ (claudeHook "$HOME/.claude/hooks/audit_compaction.sh") ];
      }
    ];

    SessionStart = [
      {
        matcher = "compact|resume";
        hooks = [ (claudeHook "$HOME/.claude/hooks/audit_compaction.sh") ];
      }
    ];
  };

  codexHooks = {
    hooks = {
      UserPromptSubmit = [
        {
          hooks = [
            (codexHook "$HOME/.codex/hooks/adapt_guard_secret_content.sh prompt"
              "Scanning prompt for sensitive information"
              30
            )
          ];
        }
      ];

      PreToolUse = [
        {
          matcher = shellMatcher;
          hooks = [
            (codexHook
              "$HOME/.codex/hooks/adapt_shell_command.sh $HOME/.claude/hooks/guard_forbidden_commands.sh"
              "Checking forbidden command prefixes"
              30
            )
            (codexHook "$HOME/.codex/hooks/adapt_shell_command.sh $HOME/.claude/hooks/guard_secret_commit.sh"
              "Checking staged files for secrets"
              30
            )
            (codexHook "$HOME/.codex/hooks/adapt_shell_command.sh $HOME/.claude/hooks/guard_dangerous_git.sh"
              "Checking for dangerous git operations"
              30
            )
            (codexHook "$HOME/.codex/hooks/adapt_shell_command.sh $HOME/.claude/hooks/guard_allowed_commands.sh"
              "Checking command policy"
              30
            )
          ];
        }
        {
          matcher = editMatcher;
          hooks = [
            (codexHook "$HOME/.claude/hooks/guard_harness_files.sh" "Checking harness boundaries" 30)
            (codexHook "$HOME/.codex/hooks/adapt_guard_secret_content.sh apply-patch"
              "Scanning patch for sensitive information"
              30
            )
          ];
        }
      ];

      PostToolUse = [
        {
          matcher = editMatcher;
          hooks = [
            (codexHook "$HOME/.codex/hooks/adapt_lint_format.sh" "Running lint/format hooks" 120)
          ];
        }
        {
          matcher = ".";
          hooks = [
            (codexHook "$HOME/.claude/hooks/audit_tool_call.sh" "Logging tool call" 10)
          ];
        }
      ];
    };
  };
}
