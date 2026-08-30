{
  config,
  pkgs,
  lib,
  username,
  dotfilesDir,
  unstable,
  llm-agents,
  appleMailCliPackage,
  gogCliPackage,
  hermesAgentPackage,
  herdrPackage,
  histerPackage,
  histerServerUrl,
  agent-harness,
  system,
  enableMoshiService,
  ...
}:
let
  link = path: config.lib.file.mkOutOfStoreSymlink "${dotfilesDir}/${path}";
  esaCliPackage = pkgs.callPackage ../packages/esa_cli.nix { };
  ghStackPackage = pkgs.callPackage ../packages/gh_stack.nix { };
  gitWtPackage = unstable.callPackage ../packages/git_wt.nix { gitWt = unstable.git-wt; };
  rootsPackage = pkgs.callPackage ../packages/roots.nix { };
  terminalBrowserPackage = pkgs.callPackage ../packages/terminal_browser.nix { };
  codexPackage = llm-agents.packages.${system}.codex;
  agentHarnessPackage = agent-harness.packages.${system}.default;
  moshiHookGenerator = pkgs.callPackage ../packages/moshi_hook.nix { };
  moshiHookRuntime = "/opt/homebrew/bin/moshi-hook";
  moshiLifecycle = pkgs.writeTextFile {
    name = "manage-moshi-hook";
    destination = "/bin/manage_moshi_hook";
    executable = true;
    text = builtins.readFile ../../scripts/moshi/manage_moshi_hook.sh;
  };
  moshiLifecycleBin = "${moshiLifecycle}/bin/manage_moshi_hook";
  moshiLifecycleEnvironment = {
    JQ_BIN = lib.getExe pkgs.jq;
    MOSHI_HOOK_BIN = moshiHookRuntime;
    MOSHI_RUNTIME_STATE_FILE = "${config.xdg.stateHome}/moshi-hook/runtime_path";
    REALPATH_BIN = lib.getExe' pkgs.coreutils "realpath";
    SLEEP_BIN = lib.getExe' pkgs.coreutils "sleep";
  };
  repoCommand = pkgs.writeShellScriptBin "repo" ''
    exec "${dotfilesDir}/github/repo.sh" "$@"
  '';
  secretaryCli = pkgs.writeShellApplication {
    name = "secretary";
    runtimeInputs = [ hermesAgentPackage ];
    text = ''
      exec hermes -p secretary "$@"
    '';
  };
  zshCacheBuilder = pkgs.writeText "build_cache.sh" (builtins.readFile ../../zsh/build_cache.sh);
  herdrSkill = pkgs.runCommand "herdr-skill" { } ''
    set -euxCo pipefail
    mkdir -p "$out"
    ${lib.getExe herdrPackage} --skill >| "$out/SKILL.md"
  '';
  generateHookBundle =
    name: spec:
    pkgs.runCommand name { } ''
      set -euxCo pipefail
      ${lib.getExe agentHarnessPackage} generate-hook-bundle \
        --spec ${spec} \
        --output "$out"
    '';
  herdrHookSpec = pkgs.writeText "herdr-hook-bundle-spec.json" (
    builtins.toJSON {
      version = 1;
      installers =
        map
          (provider: {
            executable = lib.getExe herdrPackage;
            arguments = [
              "integration"
              "install"
              provider
            ];
          })
          [
            "claude"
            "codex"
          ];
    }
  );
  moshiHookSpec = pkgs.writeText "moshi-hook-bundle-spec.json" (
    builtins.toJSON {
      version = 1;
      installers = [
        {
          executable = lib.getExe moshiHookGenerator;
          arguments = [
            "install"
            "--target"
            "claude,codex"
          ];
        }
      ];
      command_replacements = [
        {
          from = lib.getExe moshiHookGenerator;
          to = moshiHookRuntime;
        }
      ];
    }
  );
  herdrHookBundle = generateHookBundle "herdr-hook-bundle" herdrHookSpec;
  moshiHookBundle = generateHookBundle "moshi-hook-bundle" moshiHookSpec;
  herdrZshCompletion = pkgs.runCommand "herdr-zsh-completion" { } ''
    set -euxCo pipefail
    mkdir -p "$out/share/zsh/site-functions"
    ${lib.getExe herdrPackage} completion zsh >| "$out/share/zsh/site-functions/_herdr"
  '';
  herdrCompatibleCodex = pkgs.writeShellScriptBin "codex" ''
    export CODEX_EXECUTABLE_PATH="$HOME/.local/bin/codex"
    export DISABLE_AUTOUPDATER=1
    exec -a codex ${codexPackage}/bin/codex "$@"
  '';
  herdrPlugins = [
    {
      id = "persiyanov.reviewr";
      source = "persiyanov/herdr-reviewr";
      rev = "8db4c8e4a0a287a63b8265aea7da4bfe7a8d0f3a";
    }
  ];
  herdrPluginArgs = lib.escapeShellArgs (
    lib.concatMap (plugin: [
      plugin.id
      plugin.source
      plugin.rev
    ]) herdrPlugins
  );
in
{
  home = {
    inherit username;
    homeDirectory = "/Users/${username}";
    stateVersion = "25.11";
  };

  home.packages = with pkgs; [
    # Shell and environment
    carapace
    direnv
    dotenvx
    starship
    zoxide
    zsh-abbr
    zsh-autosuggestions
    zsh-completions
    zsh-fast-syntax-highlighting

    # Files and search
    bat
    dust
    eza
    fd
    fzf
    histerPackage
    ripgrep

    # Editors
    tree-sitter

    # Developer workflow
    ghq
    gitWtPackage
    herdrPackage
    herdrZshCompletion
    just
    mosh
    repoCommand
    rootsPackage
    secretaryCli
    terminalBrowserPackage

    # Code quality
    actionlint
    autocorrect
    commitlint
    dprint
    lefthook
    ls-lint
    # prettierd: used for markdown because dprint-plugin-markdown hardcodes 2-space list indent.
    # tabWidth:4 in ~/.prettierrc gives 4-space list nesting to match Obsidian.
    # TODO: replace with dprint once https://github.com/dprint/dprint-plugin-markdown/pull/176 merges.
    prettierd

    # Content and media
    esaCliPackage
    ffmpeg

    # Personal secretary integrations
    appleMailCliPackage
    gogCliPackage

    # AI coding agents
    llm-agents.packages.${system}.claude-code
    herdrCompatibleCodex
    hermesAgentPackage
    unstable.opencode
    unstable.pi-coding-agent

    # Nix tooling
    deadnix
    home-manager
    nixd
    nixfmt-rfc-style
    statix
    vulnix

    # Shell tooling
    bash-language-server
    bats
    shellcheck
    shfmt

    # Python tooling
    uv

    # Rust tooling
    rustup

    # TypeScript tooling
    nodePackages."@antfu/ni"
    unstable.nodejs_24
    unstable.oxfmt
    unstable.oxlint
    pnpm
    unstable.tsgolint
    typescript
    typescript-language-server

    # Lua tooling
    lua-language-server
    selene
    stylua

    # LaTeX tooling
    ltex-ls
    tex-fmt
    texlab

    # Apple development
    xcodes
  ];

  # Zsh plugin file generated by Nix（case B: .zshrc stays as dotfile symlink）
  # ${pkgs.xxx} is expanded to /nix/store/... at evaluation time
  home.file.".config/zsh/nix-plugins.zsh".text = ''
    source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
    source ${pkgs.zsh-fast-syntax-highlighting}/share/zsh/plugins/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh
    source ${pkgs.zsh-abbr}/share/zsh/zsh-abbr/zsh-abbr.zsh
  '';

  programs = {
    neovim = {
      enable = true;
      plugins = [ pkgs.vimPlugins.lazy-nvim ];
    };

    git = {
      enable = true;
      settings = {
        user = {
          name = "furedea";
          email = "132188853+furedea@users.noreply.github.com";
          signingkey = "~/.ssh/id_ed25519.pub";
        };
        gpg.format = "ssh";
        commit.gpgsign = true;
        tag.gpgsign = true;
        init.defaultBranch = "main";
        credential.helper = "osxkeychain";
        column.ui = "auto";
        branch.sort = "-committerdate";
        tag.sort = "version:refname";
        diff = {
          algorithm = "histogram";
          colorMoved = "plain";
          mnemonicPrefix = true;
          renames = true;
        };
        pull.rebase = true;
        push = {
          default = "simple";
          autoSetupRemote = true;
          followTags = true;
        };
        fetch = {
          prune = true;
          pruneTags = true;
          all = true;
        };
        help.autocorrect = "prompt";
        commit.verbose = true;
        rerere = {
          enabled = true;
          autoupdate = true;
        };
        core = {
          fsmonitor = true;
          untrackedCache = true;
        };
        rebase = {
          autoSquash = true;
          autoStash = true;
          updateRefs = true;
        };
        merge.conflictstyle = "zdiff3";
        transfer.fsckObjects = true;
        fetch.fsckObjects = true;
        receive.fsckObjects = true;
        status.short = true;
        status.branch = true;
        alias.cc = "!f() { tmpf=$(mktemp) && codex exec --full-auto -o \"$tmpf\" 'Review the staged diff and generate a Conventional Commits message. Output ONLY the commit message, nothing else.' && git commit -F \"$tmpf\"; rm -f \"$tmpf\"; }; f";
        alias.wtd = "wt -D";
      };
    };

    delta = {
      enable = true;
      enableGitIntegration = true;
      options = {
        side-by-side = true;
        navigate = true;
        hyperlinks = true;
        true-color = "always";
        syntax-theme = "ansi";
        line-numbers = true;
        features = "decorations unobtrusive-line-numbers";
        plus-style = "#a6e3a1";
        plus-emph-style = "bold #a6e3a1";
        minus-style = "#f38ba8";
        minus-emph-style = "bold #f38ba8";
        zero-style = "normal";
        hunk-header-style = "bold #89b4fa";
        decorations = {
          commit-decoration-style = "bold #f9e2af box ul";
          file-style = "bold #89b4fa ul";
          file-decoration-style = "none";
          hunk-header-decoration-style = "#94e2d5 box ul";
        };
        unobtrusive-line-numbers = {
          line-numbers-left-format = "{nm:>4}┊";
          line-numbers-right-format = "{np:>4}│";
          line-numbers-left-style = "#6c7086";
          line-numbers-right-style = "#6c7086";
          line-numbers-minus-style = "#6c7086";
          line-numbers-zero-style = "#6c7086";
          line-numbers-plus-style = "#6c7086";
        };
      };
    };

    gh = {
      enable = true;
      extensions = [ ghStackPackage ];
      settings = {
        git_protocol = "https";
        prompt = "enabled";
        aliases.co = "pr checkout";
      };
    };

    lazygit = {
      enable = true;
      settings = {
        gui = {
          nerdFontsVersion = "3";
          showIcons = true;
          expandFocusedSidePanel = true;
          showRandomTip = false;
        };
        git = {
          pagers = [
            {
              colorArg = "always";
              pager = "delta --paging=never";
            }
          ];
          branchLogCmd = "git log --graph --color=always --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' {{branchName}} --";
          allBranchesLogCmds = [
            "git log --graph --color=always --pretty='%Cred%h%Creset -%C(auto)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --all"
          ];
        };
        customCommands = [
          {
            key = "C";
            command = ''npx --yes --package czg@1.13.0 --package @commitlint/config-conventional --call 'NODE_PATH="$(dirname "$(dirname "$(command -v czg)")")''${NODE_PATH:+:$NODE_PATH}" czg' '';
            context = "files";
            loadingText = "Opening czg";
            output = "terminal";
          }
        ];
      };
    };

    direnv = {
      enable = true;
      enableZshIntegration = false; # .zshrc is a dotfile symlink; hook manually there
      nix-direnv.enable = true;
    };

    atuin = {
      enable = true;
      package = unstable.atuin;
      enableZshIntegration = false; # .zshrc が dotfile のため手動 eval を使う
      settings = {
        enter_accept = true;
        sync.records = true;
      };
    };

    agent-harness = {
      enable = true;
      package = agentHarnessPackage;
      source = ../../agents;
      skills.herdr = herdrSkill;
      hooks = {
        herdr = herdrHookBundle;
        moshi = moshiHookBundle;
      };
    };

    yazi = {
      enable = true;
      plugins = with pkgs.yaziPlugins; {
        inherit
          git
          smart-enter
          smart-filter
          vcs-files
          ;
      };
      initLua = ''
        require("git"):setup()
      '';
      settings = {
        mgr.show_hidden = true;
        plugin.prepend_fetchers = [
          {
            id = "git";
            name = "*";
            run = "git";
          }
          {
            id = "git";
            name = "*/";
            run = "git";
          }
        ];
      };
      keymap = {
        mgr.prepend_keymap = [
          {
            on = [ "o" ];
            run = "create";
            desc = "Create a file or directory";
          }
          {
            on = [ "<Esc>" ];
            run = "quit";
            desc = "Quit";
          }
          {
            on = [ "l" ];
            run = "plugin smart-enter";
            desc = "Enter directory or open file";
          }
          {
            on = [ "F" ];
            run = "plugin smart-filter";
            desc = "Smart filter";
          }
          {
            on = [
              "g"
              "c"
            ];
            run = "plugin vcs-files";
            desc = "Show Git file changes";
          }
        ];
      };
    };

  };

  launchd.agents = {
    ssh-agent-loader = {
      enable = true;
      config = {
        ProgramArguments = [
          "/usr/bin/ssh-add"
          "--apple-load-keychain"
        ];
        ProcessType = "Background";
        RunAtLoad = true;
      };
    };
  }
  // lib.optionalAttrs enableMoshiService {
    moshi-hook = {
      enable = true;
      config = {
        ProgramArguments = [
          moshiLifecycleBin
          "serve"
        ];
        EnvironmentVariables = moshiLifecycleEnvironment;
        KeepAlive = true;
        LimitLoadToSessionType = "Aqua";
        ProcessType = "Background";
        RunAtLoad = true;
      };
    };
    moshi-hook-updater = {
      enable = true;
      config = {
        ProgramArguments = [
          moshiLifecycleBin
          "restart-after-update"
        ];
        EnvironmentVariables = moshiLifecycleEnvironment;
        LimitLoadToSessionType = "Aqua";
        ProcessType = "Background";
        ThrottleInterval = 30;
        WatchPaths = [ "/opt/homebrew/Cellar/moshi-hook" ];
      };
    };
  };

  home.activation = {
    initializeHermesSecretary = lib.hm.dag.entryBetween [ "linkGeneration" ] [ "writeBoundary" ] ''
      if [ ! -d "$HOME/.hermes/profiles/secretary" ]; then
        ${lib.getExe hermesAgentPackage} profile create secretary --no-skills --no-alias
        /bin/rm -f "$HOME/.hermes/profiles/secretary/SOUL.md"
      fi
    '';
    zshCache = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
      BASH_XTRACEFD=9 \
        "${pkgs.bash}/bin/bash" \
        "${zshCacheBuilder}" \
        "${pkgs.zsh}/bin/zsh" \
        "${config.home.homeDirectory}/.zshrc" \
        "${config.xdg.cacheHome}/zsh/.zcompdump" \
        9>/dev/null
    '';
    rustupInit = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      ${pkgs.rustup}/bin/rustup toolchain install stable --no-self-update 2>/dev/null || true
    '';
    uvPythonInstall = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      ${pkgs.uv}/bin/uv python install 2>/dev/null || true
    '';
    sshDirectoryPermissions = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      if [ -d "$HOME/.ssh" ]; then
        /bin/chmod 0700 "$HOME/.ssh"
      fi
    '';
    sshIdentityCheck = lib.hm.dag.entryAfter [ "sshDirectoryPermissions" ] ''
      if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
        printf '%s\n' \
          'SSH identity is missing. Create it interactively with a non-empty passphrase:' \
          '  /usr/bin/ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519"' \
          '  /usr/bin/ssh-add --apple-use-keychain "$HOME/.ssh/id_ed25519"'
      elif /usr/bin/ssh-keygen -y -P "" -f "$HOME/.ssh/id_ed25519" >/dev/null 2>&1; then
        printf '%s\n' \
          'SSH identity has no passphrase. Protect it and store the passphrase in the macOS Keychain:' \
          '  /usr/bin/ssh-keygen -p -f "$HOME/.ssh/id_ed25519"' \
          '  /usr/bin/ssh-add --apple-use-keychain "$HOME/.ssh/id_ed25519"'
      fi
    '';
    herdrPlugins = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
      PATH="${lib.makeBinPath [ pkgs.git ]}:/usr/bin:/bin" \
        BASH_XTRACEFD=9 \
        HERDR_BIN="${herdrPackage}/bin/herdr" \
        JQ_BIN="${pkgs.jq}/bin/jq" \
        HERDR_PLUGIN_SYNC_STATE_FILE="${config.xdg.stateHome}/home-manager/herdr_plugins" \
        ${pkgs.bash}/bin/bash \
        "${config.home.homeDirectory}/.local/libexec/sync_herdr_plugins.sh" \
        ${herdrPluginArgs} 9>/dev/null
    '';
    moshiHomebrewServiceMigration = lib.mkIf enableMoshiService (
      lib.hm.dag.entryBetween [ "setupLaunchAgents" ] [ "writeBoundary" ] ''
        BASH_XTRACEFD=9 \
          BREW_BIN="/opt/homebrew/bin/brew" \
          MOSHI_LEGACY_SERVICE_FILE="$HOME/Library/LaunchAgents/homebrew.mxcl.moshi-hook.plist" \
          "${moshiLifecycleBin}" migrate-homebrew-service 9>/dev/null
      ''
    );
  };

  # lazygit reads XDG_CONFIG_HOME/lazygit/config.yml first when XDG_CONFIG_HOME is set
  # in the shell, but home-manager writes to ~/Library/Application Support/lazygit/ on macOS.
  # Mirror to the XDG path so the home-manager-generated config is actually used.
  xdg.configFile."lazygit/config.yml".source =
    config.home.file."Library/Application Support/lazygit/config.yml".source;
  xdg.configFile."agent-harness/bin/timeout".source = lib.getExe' pkgs.coreutils "timeout";

  home.file = {
    # Zsh（dotfileに実ファイル，直接編集可能）
    ".zshrc".source = link "zsh/.zshrc";
    ".zshenv".source = link "zsh/.zshenv";
    ".zprofile".source = link "zsh/.zprofile";

    # Bash
    ".bashrc".source = link "bash/.bashrc";

    # Git ignore
    ".config/git/ignore".source = link "git/ignore";

    # Hister client
    "Library/Preferences/hister/config.yml".text = builtins.toJSON {
      server.base_url = histerServerUrl;
    };

    # Neovim（多ファイル・頻繁に編集）
    ".config/nvim".source = link "nvim";

    # Starship
    ".config/starship.toml".source = link "starship/starship.toml";

    # Vim
    ".vimrc".source = link "vim/.vimrc";

    # dprint (global formatter config — dprint looks for ~/dprint.json by default)
    "dprint.json".source = link "dprint/dprint.json";

    # prettierd (global formatter config)
    ".prettierrc".source = link "prettier/.prettierrc";

    # EditorConfig (global fallback for projects without their own)
    ".editorconfig".source = link ".editorconfig";

    # macOS GUI 設定
    ".config/ghostty/config".source = link "ghostty/config";
    ".config/karabiner/karabiner.json".source = link "karabiner/karabiner.json";
    ".config/herdr/config.toml".source = link "herdr/config.toml";
    ".config/herdr/plugins/config/persiyanov.reviewr/config.toml".source = link "herdr/reviewr.toml";
    ".local/libexec/herdr_merge_pull_request.sh".source = link "herdr/merge_pull_request.sh";
    ".local/libexec/sync_herdr_plugins.sh".source = link "herdr/sync_plugins.sh";

    # Hermes secretary files remain editable by Hermes and visible to Git.
    ".hermes/profiles/secretary/SOUL.md".source = link "hermes/secretary/SOUL.md";
    ".hermes/profiles/secretary/skills/secretary".source = link "hermes/secretary/skills/secretary";
  };
}
