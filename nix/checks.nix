# Evaluate configuration contracts in Nix; executable integration remains in Bats.
#
# `evaluation` checks only read option values, so they run on any host: the
# runner derivation is a bare `touch` and the contracts are asserted at
# evaluation time. `darwinOnly` checks build or execute Darwin binaries and
# are exposed for aarch64-darwin alone.
{
  pkgs,
  runner,
  lib,
  home,
  homeConfigurations,
  darwin,
  inputs,
}:
let
  names = packages: map (package: package.pname or package.name) packages;
  versions =
    name: packages:
    map (package: package.version) (builtins.filter (package: (package.pname or "") == name) packages);
  homeNames = names home.home.packages;
  mbp = darwin.mbp.config;
  mba = darwin.mba.config;
  mbpHome = mbp.home-manager.users.kaito;
  mbaHome = mba.home-manager.users.kaito;
  moshi = mbpHome.launchd.agents.moshi-hook.config;
  moshiVersion = (pkgs.callPackage ./packages/moshi_hook.nix { }).version;
  codexPackage = pkgs.callPackage ./packages/codex.nix { };
  agentDesktopPackage = pkgs.callPackage ./packages/agent_desktop.nix { };
  chromeExecutable = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  antigravityPackage = inputs.llm-agents.packages.${pkgs.stdenv.hostPlatform.system}.antigravity-cli;
  antigravityWrapperText = lib.concatMapStrings (package: package.text or "") (
    builtins.filter (package: (package.name or "") == "agy") home.home.packages
  );
  codexWrapperText =
    (builtins.head (builtins.filter (package: (package.name or "") == "codex") home.home.packages))
    .text;
  hister = mbp.launchd.user.agents.hister.serviceConfig;
  t3Service = mbpHome.launchd.agents.t3-server.config;
  t3Package = builtins.head (
    builtins.filter (package: (package.pname or "") == "t3code") mbpHome.home.packages
  );
  t3DesktopPackage = builtins.head (
    builtins.filter (
      package: (package.pname or package.name or "") == "t3code-desktop"
    ) mbpHome.home.packages
  );
  t3ServicePath = lib.splitString ":" t3Service.EnvironmentVariables.PATH;
  t3ServiceState = "${mbpHome.home.homeDirectory}/.t3";
  claudePackage = inputs.llm-agents.packages.${pkgs.stdenv.hostPlatform.system}.claude-code;
  lsp = home.launchd.agents.lspmux;
  lspSettings =
    builtins.fromTOML
      home.home.file."Library/Application Support/lspmux/config.toml".text;
  telemetryOptOuts = {
    GH_TELEMETRY = "disabled";
    GH_STACK_NO_UPDATE_NOTIFIER = "1";
    HOMEBREW_NO_ANALYTICS = "1";
    DSH_TELEMETRY_DISABLED = "1";
    AGENT_BROWSER_NO_VERSION_CHECK = "1";
  };
  telemetryOptOutExports = lib.mapAttrsToList (
    name: value: "export ${name}=${value}"
  ) telemetryOptOuts;
  codexSettings = home.programs.agent-harness.codex.composedSettings;
  lspmuxSocket = "${home.home.homeDirectory}/Library/Application Support/lspmux/lspmux.sock";
  serviceNames = config: builtins.attrNames config.launchd.agents;
  hasAll = expected: actual: builtins.all (value: builtins.elem value actual) expected;
  shellEditorDefinitions = [
    "export EDITOR="
    "export VISUAL="
  ];
  shellConfigs = map builtins.readFile [
    ../bash/.bashrc
    ../zsh/.zshrc
  ];
  noSecrets =
    environment:
    builtins.all (
      name: builtins.match ".*(token|password|credential|secret).*" (lib.toLower name) == null
    ) (builtins.attrNames environment);
  cacheTrusted =
    config:
    (config.nix.settings.extra-substituters or [ ]) == [ "https://cache.numtide.com" ]
    &&
      (config.nix.settings.extra-trusted-public-keys or [ ])
      == [ "niks3.numtide.com-1:DTx8wZduET09hRmMtKdQDxNNthLQETkc/yaX7M4qK0g=" ];
  check =
    name: contracts:
    let
      failures = builtins.attrNames (lib.filterAttrs (_: valid: !valid) contracts);
    in
    assert lib.assertMsg (failures == [ ]) (
      "Failed dotfiles contracts: " + lib.concatStringsSep ", " failures
    );
    runner.runCommand name { passthru = { inherit contracts; }; } ''
      touch "$out"
    '';
  nvimLogFile = "${home.xdg.stateHome}/agent-harness/nvim.log";
  ghConfigDir = home.programs.agent-harness.github.agentToken.configDir;
  claudeEnv = home.programs.agent-harness.claude.composedSettings.env;
  codexEnv = home.programs.agent-harness.codex.composedSettings.shell_environment_policy.set;
  # Forcing the derivation path evaluates the whole system without building it.
  evaluatesToDerivation =
    config:
    lib.hasSuffix ".drv" (builtins.unsafeDiscardStringContext config.system.build.toplevel.drvPath);
  # T3 settings fixtures and the documents the user chose for them (Issue #489, step 5).
  t3StopRule = {
    key = "ctrl+c";
    command = "thread.stop";
    when = "turnRunning && !terminalFocus";
  };
  t3UnrelatedRule = {
    key = "mod+b";
    command = "sidebar.toggle";
  };
  t3ManagedClientSettings = {
    notificationMode = "notifications-and-sound";
    inAppNotificationsEnabled = true;
    confirmThreadUnpin = true;
    confirmThreadArchive = true;
    confirmThreadDelete = true;
    confirmQuit = "double-click";
    language = "ja";
    fontFamilyCode = "JetBrains Mono";
    mathRenderingEnabled = true;
    composerRichTextEnabled = false;
    diffLayout = "split";
    browserAutoShowFloatingPreview = false;
  };
  t3ManagedThreadDetails = {
    openIn = false;
    scripts = false;
    servers = false;
    automations = false;
    usage = true;
    context = true;
  };
  t3ManagedServerSettings = {
    enableAgentBrowserAccess = false;
    defaultAutoPull = true;
    defaultModelSelection = {
      instanceId = "claudeAgent";
      model = "claude-opus-5-5";
      options = [
        {
          id = "effort";
          value = "medium";
        }
      ];
    };
    fallbackModelSelection = {
      instanceId = "codex";
      model = "gpt-6.2-sol";
      options = [
        {
          id = "reasoningEffort";
          value = "medium";
        }
      ];
    };
    defaultRuntimeMode = "auto";
    snoozeLimitedThreads = true;
    autoResumeLimitedThreads = true;
    addProjectBaseDirectory = "~/ghq";
    ghqCloneLayout = true;
    removeAgentCreditsOnMerge = true;
    pullRequestMergeMethod = "squash";
  };
  t3Fixtures = {
    keybindings = pkgs.writeText "keybindings.json" (
      builtins.toJSON [
        t3UnrelatedRule
        {
          key = "escape";
          command = "thread.stop";
        }
        t3StopRule
      ]
    );
    serverSettings = builtins.toJSON {
      providerInstances.antigravity.driver = "antigravity";
      idleCompaction = "onReturn";
      defaultRuntimeMode = "full-access";
      storageCleanup = {
        worktreeOnMerge = false;
        worktreeOnArchive = true;
      };
      defaultModelSelection = {
        instanceId = "codex";
        model = "gpt-5";
        options = [
          {
            id = "reasoningEffort";
            value = "high";
          }
        ];
      };
    };
    clientSettings = builtins.toJSON {
      language = "en";
      fontSizeCode = 13;
      threadDetailsItems = {
        openIn = true;
        branch = false;
      };
    };
  };
  t3Expected = {
    mbpKeybindings = builtins.toJSON [
      t3UnrelatedRule
      t3StopRule
    ];
    mbpServerSettings = builtins.toJSON (
      t3ManagedServerSettings
      // {
        providerInstances.antigravity.driver = "antigravity";
        idleCompaction = "onReturn";
        storageCleanup = {
          worktreeOnMerge = true;
          worktreeOnDelete = true;
          worktreeOnArchive = true;
        };
      }
    );
    mbpClientSettings = builtins.toJSON (
      t3ManagedClientSettings
      // {
        fontSizeCode = 13;
        threadDetailsItems = t3ManagedThreadDetails // {
          branch = false;
        };
      }
    );
    mbpDesktopSettings = builtins.toJSON { localEnvironmentEnabled = false; };
    mbaKeybindings = builtins.toJSON [ t3StopRule ];
  };
in
{
  evaluation = {
    home-configuration = check "home-configuration" {
      # The composed settings are what the harness renders into settings.json and config.toml.
      agent-claude-env-managed-paths =
        (claudeEnv.NVIM_LOG_FILE or null) == nvimLogFile
        && (claudeEnv.GH_CONFIG_DIR or null) == ghConfigDir;
      agent-codex-env-managed-paths =
        (codexEnv.NVIM_LOG_FILE or null) == nvimLogFile && (codexEnv.GH_CONFIG_DIR or null) == ghConfigDir;
      # Default-on telemetry and update checks stay off in login shells and in agents that skip .zshenv.
      telemetry-opt-outs-in-agent-envs =
        builtins.all (name: (claudeEnv.${name} or null) == telemetryOptOuts.${name}) (
          builtins.attrNames telemetryOptOuts
        )
        && builtins.all (name: (codexEnv.${name} or null) == telemetryOptOuts.${name}) (
          builtins.attrNames telemetryOptOuts
        );
      telemetry-opt-outs-in-zshenv = builtins.all (
        line: lib.hasInfix "${line}\n" (builtins.readFile ../zsh/.zshenv)
      ) telemetryOptOutExports;
      codex-analytics-disabled =
        (codexSettings.analytics.enabled or true) == false
        && (codexSettings.otel.metrics_exporter or null) == "none"
        && (codexSettings.feedback.enabled or true) == false;
      codex-no-update-check = (codexSettings.check_for_update_on_startup or true) == false;
      omlx-service-no-hub-telemetry =
        lib.hasInfix "HF_HUB_DISABLE_TELEMETRY=1\n"
          home.home.file.".homebrew/services/omlx.env".text;
      # agy's closed binary accepts a hidden global flag; the wrapper replaces the package on PATH.
      antigravity-telemetry-disabled =
        lib.hasInfix "--disable_telemetry" antigravityWrapperText
        && lib.hasInfix (builtins.unsafeDiscardStringContext "${antigravityPackage}/bin/agy") antigravityWrapperText
        && !(builtins.elem "antigravity-cli" homeNames);
      claude-feedback-disabled =
        (claudeEnv.DISABLE_FEEDBACK_COMMAND or null) == "1"
        && (claudeEnv.CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY or null) == "1"
        && !(claudeEnv ? CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC);
      codex-daemon-auto-start-disabled = (codexSettings.features.daemon_auto_start or true) == false;
      claude-telemetry-disabled =
        (claudeEnv.DISABLE_TELEMETRY or null) == "1"
        && (claudeEnv.DISABLE_ERROR_REPORTING or null) == "1"
        && !(claudeEnv ? CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC);
      gh-config-telemetry-disabled = (home.programs.gh.settings.telemetry or null) == "disabled";
      atuin-no-update-check = (home.programs.atuin.settings.update_check or true) == false;
      lazygit-no-update-check = (home.programs.lazygit.settings.update.method or null) == "never";
      lspmux-unix-socket-only =
        (lspSettings.listen or null) == lspmuxSocket && (lspSettings.connect or null) == lspmuxSocket;
      carapace-no-uninstalled-bridge = !(lib.hasInfix "inshellisense" (builtins.readFile ../zsh/.zshrc));
      hooks-compose-herdr-and-moshi =
        builtins.attrNames home.programs.agent-harness.hooks == [
          "herdr"
          "moshi"
        ];
      # Sandboxed agents cannot write ~/.local/state/nvim, so Neovim would drop nvim.log in the workspace.
      agent-nvim-log-in-writable-state =
        let
          claude = home.programs.agent-harness.claude.composedSettings;
        in
        claude.env.NVIM_LOG_FILE == nvimLogFile
        && builtins.elem "~/.local/state/agent-harness" claude.sandbox.filesystem.allowWrite;
      github-stacked-pr-extension =
        names home.programs.gh.extensions == [
          "gh-stack"
          "gh-dash"
        ];
      neovim-nix-managed-plugin-loader = names home.programs.neovim.plugins == [ "lazy.nvim" ];
      yazi-bats-icon =
        (home.programs.yazi.theme.icon.prepend_exts or [ ]) == [
          {
            name = "bats";
            text = "";
          }
        ];
      ssh-no-keychain-loader = !(home.launchd.agents ? ssh-agent-loader);
      # ~/.ssh/config holds private host details and stays out of this public repository.
      ssh-client-config-unmanaged = !(home.home.file ? ".ssh/config");
      git-signs-with-ssh-public-key =
        home.programs.git.settings.user.signingkey == "~/.ssh/id_ed25519.pub"
        && home.programs.git.settings.gpg.format == "ssh";
      ssh-identity-creation-left-to-user = !(home.home.activation ? sshKeyGen);
      zsh-cache-after-startup-links = home.home.activation.zshCache.after == [ "linkGeneration" ];
      global-language-toolchains = hasAll [
        "python3"
        "uv"
        "nodejs"
        "zizmor"
        "pnpm"
        "cargo"
        "rustc"
        "clippy"
        "rustfmt"
      ] homeNames;
      pnpm-shared-virtual-store =
        home.xdg.configFile."pnpm/config.yaml".text == ''
          storeDir: ${home.xdg.dataHome}/pnpm/store
          enableGlobalVirtualStore: true
          updateNotifier: false
        '';
      no-mutable-language-installers =
        !(builtins.elem "rustup" homeNames)
        && !(home.home.activation ? rustupInit)
        && !(home.home.activation ? uvPythonInstall);
      managed-automation-python =
        toString home.xdg.configFile."dotfiles/bin/python3".source
        == lib.getExe inputs.nixpkgs-unstable.legacyPackages.${pkgs.stdenv.hostPlatform.system}.python315;
      agent-packages =
        builtins.filter (
          name:
          builtins.elem name [
            "agy"
            "claude-code"
            "codex"
            "herdr"
          ]
        ) homeNames == [
          "herdr"
          "agy"
          "claude-code"
          "codex"
        ];
      automation-cli-packages =
        versions "agent-browser" home.home.packages != [ ]
        && versions "agent-desktop" home.home.packages == [ agentDesktopPackage.version ];
      automation-cli-skills = hasAll [
        "agent-browser"
        "agent-desktop"
      ] (builtins.attrNames home.programs.agent-harness.skills);
      # agent-browser on Darwin bundles no browser; it must point at the cask-installed Chrome.
      agent-browser-uses-cask-chrome =
        lib.hasInfix ''export AGENT_BROWSER_EXECUTABLE_PATH="${chromeExecutable}"'' (
          builtins.readFile ../zsh/.zshenv
        )
        && lib.hasInfix ''"google-chrome"'' mbp.homebrew.brewfile;
      # Building codexPackage runs its install check: the vendor Developer ID signature must survive.
      codex-official-signed-release =
        lib.hasInfix "/releases/download/rust-v${codexPackage.version}/" codexPackage.src.url
        && lib.hasInfix (builtins.unsafeDiscardStringContext "${codexPackage}/bin/codex") codexWrapperText
        && !(lib.hasInfix "llm-agents" codexWrapperText);
      no-unguarded-agent-packages = !(builtins.elem "opencode" homeNames);
      # lefthook before 2.1.6 runs hook commands under a pty, which agent sandboxes deny.
      sandbox-compatible-git-hooks =
        let
          lefthookVersions = versions "lefthook" home.home.packages;
        in
        lefthookVersions != [ ]
        && builtins.all (version: lib.versionAtLeast version "2.1.6") lefthookVersions;
      commit-message-alias-avoids-removed-codex-flag =
        !(lib.hasInfix "--full-auto" home.programs.git.settings.alias.cc);
      shared-agent-input =
        inputs ? llm-agents
        && !(inputs ? nix-claude-code)
        && !(inputs ? codex-cli-nix)
        && !(inputs ? herdr);
      terminal-browser-version = versions "terminal-browser" home.home.packages == [ "0.6.0" ];
      plugin-sync-failures-propagate = !(lib.hasInfix "|| true" home.home.activation.herdrPlugins.data);
      plugin-sync-has-git =
        lib.hasInfix "-git-" home.home.activation.herdrPlugins.data
        && lib.hasInfix "/bin:/usr/bin:/bin" home.home.activation.herdrPlugins.data;
      lspmux-persistent = lsp.enable && lsp.config.RunAtLoad && lsp.config.KeepAlive;
      lspmux-server =
        lib.hasPrefix "/nix/store/" (builtins.head lsp.config.ProgramArguments)
        && builtins.elemAt lsp.config.ProgramArguments 1 == "server"
        && builtins.elem "lspmux" homeNames;
      rust-analyzer-unwrapped = lib.hasInfix "rust-analyzer-unwrapped" (
        toString home.home.file.".local/bin/rust-analyzer".source
      );
      lspmux-timeout = lspSettings.instance_timeout == 300;
      lspmux-project-environment = hasAll [
        "PATH"
        "RUSTUP_TOOLCHAIN"
        "RUSTC"
        "RUST_SRC_PATH"
        "NIX_CFLAGS_COMPILE"
        "SDKROOT"
      ] lspSettings.pass_environment;
    };

    host-configuration = check "host-configuration" {
      binary-cache-trust = cacheTrusted mbp && cacheTrusted mba;
      no-shell-specific-editor-defaults = builtins.all (
        source: builtins.all (definition: !(lib.hasInfix definition source)) shellEditorDefinitions
      ) shellConfigs;
      zsh-user-owned-completion = !mba.programs.zsh.enableGlobalCompInit;
      zsh-no-bash-completion = !mba.programs.zsh.enableBashCompletion;
      zsh-starship-prompt = mba.programs.zsh.promptInit == "";
      no-homebrew-zsh-integration = !mba.nix-homebrew.enableZshIntegration;
      no-homebrew-moshi =
        !(lib.hasInfix "moshi-hook" mba.homebrew.brewfile)
        && !(lib.hasInfix "rjyo/moshi" mba.homebrew.brewfile);
      homebrew-analytics-disabled =
        (mbp.homebrew.onActivation.extraEnv.HOMEBREW_NO_ANALYTICS or null) == "1"
        && (mba.homebrew.onActivation.extraEnv.HOMEBREW_NO_ANALYTICS or null) == "1";
      noninteractive-homebrew-cleanup = mbp.homebrew.onActivation.extraFlags == [ "--force" ];
      moshi-pinned =
        versions "moshi-hook" mbpHome.home.packages == [ moshiVersion ]
        && lib.hasPrefix "/nix/store/" (toString mbpHome.home.file.".local/bin/moshi-hook".source)
        && lib.hasSuffix "/bin/moshi-hook" (toString mbpHome.home.file.".local/bin/moshi-hook".source);
      moshi-aqua = moshi.LimitLoadToSessionType == "Aqua";
      moshi-keychain-launcher =
        lib.hasSuffix "/bin/manage_moshi_hook" (builtins.head moshi.ProgramArguments)
        && builtins.tail moshi.ProgramArguments == [ "serve" ];
      moshi-keep-alive = moshi.KeepAlive;
      moshi-managed-runtime =
        lib.hasPrefix "/nix/store/" moshi.EnvironmentVariables.MOSHI_HOOK_BIN
        && lib.hasInfix "moshi-hook-${moshiVersion}/" moshi.EnvironmentVariables.MOSHI_HOOK_BIN
        && lib.hasSuffix "/bin/moshi-hook" moshi.EnvironmentVariables.MOSHI_HOOK_BIN;
      moshi-no-updater = !(mbpHome.launchd.agents ? moshi-hook-updater);
      moshi-no-environment-credentials = noSecrets moshi.EnvironmentVariables;
      moshi-only-on-mbp =
        builtins.filter (name: lib.hasPrefix "moshi-hook" name) (builtins.attrNames mbaHome.launchd.agents)
        == [ ];
      moshi-no-migration-hooks =
        builtins.filter (name: lib.hasPrefix "moshi" name) (builtins.attrNames mbpHome.home.activation)
        == [ ];
      standalone-home-services-match-host =
        builtins.all
          (
            host:
            serviceNames homeConfigurations."kaito@${host}".config
            == serviceNames darwin.${host}.config.home-manager.users.kaito
          )
          [
            "mbp"
            "mba"
          ];
      t3-service-only-on-mbp =
        mbpHome.launchd.agents ? t3-server && !(mbaHome.launchd.agents ? t3-server);
      t3-service-login-launcher =
        t3Service.RunAtLoad
        && t3Service.LimitLoadToSessionType == "Aqua"
        &&
          t3Service.ProgramArguments == [
            (lib.getExe' t3Package "t3")
            "serve"
            "--no-browser"
          ];
      # Exit 78 (the desktop owns ~/.t3) must not restart in a tight loop.
      t3-service-throttled-restart = t3Service.KeepAlive && t3Service.ThrottleInterval == 60;
      t3-service-existing-state = t3Service.EnvironmentVariables.T3CODE_HOME == t3ServiceState;
      t3-service-loopback = t3Service.EnvironmentVariables.T3CODE_HOST == "127.0.0.1";
      t3-service-own-port =
        t3Service.EnvironmentVariables.T3CODE_PORT == "3774"
        && t3Service.EnvironmentVariables.T3CODE_PORT != "3773";
      t3-service-home = t3Service.EnvironmentVariables.HOME == mbpHome.home.homeDirectory;
      t3-service-path-profiles = hasAll [
        "/etc/profiles/per-user/kaito/bin"
        "/run/current-system/sw/bin"
      ] t3ServicePath;
      t3-service-path-providers = hasAll [
        (lib.makeBinPath [ claudePackage ])
        (lib.makeBinPath [ codexPackage ])
      ] t3ServicePath;
      t3-service-path-tailscale = builtins.elem "/usr/local/bin" t3ServicePath;
      t3-service-logs-under-state =
        lib.hasPrefix "${t3ServiceState}/userdata/logs/" t3Service.StandardOutPath
        && lib.hasPrefix "${t3ServiceState}/userdata/logs/" t3Service.StandardErrorPath;
      t3-service-log-directory-activation =
        mbpHome.home.activation ? t3LogDirectory && !(mbaHome.home.activation ? t3LogDirectory);
      t3-service-no-environment-credentials = noSecrets t3Service.EnvironmentVariables;
      t3-service-mbp-stays-awake-on-charger =
        lib.hasInfix "pmset -c sleep 0" mbp.system.activationScripts.postActivation.text
        && !(lib.hasInfix "pmset -c sleep 0" mba.system.activationScripts.postActivation.text);
      hister-login-launcher =
        hister.RunAtLoad
        && lib.hasSuffix "/bin/run_hister_server" (builtins.elemAt hister.ProgramArguments 0)
        && lib.hasSuffix "/bin/hister" (builtins.elemAt hister.ProgramArguments 1)
        && builtins.elemAt hister.ProgramArguments 2 == "kaito"
        && hister.ThrottleInterval == 60;
      hister-no-generated-token = !((mbp.services.hister.settings.app or { }) ? access_token);
      hister-no-environment-credentials = noSecrets hister.EnvironmentVariables;
      hister-loopback = mbp.services.hister.settings.server.address == "127.0.0.1:4433";
      hister-https-origin =
        mbp.services.hister.settings.server.base_url == "https://mbp.tailbb556b.ts.net";
      hister-no-mba-service = !(mba.launchd.user.agents ? hister);
      hister-mba-client = builtins.elem "hister" (names mbaHome.home.packages);
      hister-mba-origin =
        (builtins.fromJSON mbaHome.home.file."Library/Preferences/hister/config.yml".text).server.base_url
        == "https://mbp.tailbb556b.ts.net";
    };

    # A broken module option in any host fails here, long before a switch builds it.
    system-configurations = check "system-configurations" {
      mbp-system-evaluates = evaluatesToDerivation mbp;
      mba-system-evaluates = evaluatesToDerivation mba;
    };
  };

  # These build or run Darwin binaries, so they cannot execute on a Linux runner.
  darwinOnly = {
    # Building the package runs the vendor signature check on the release binary.
    codex-official-signed = codexPackage;

    # Building the package runs versionCheckHook against agent-desktop --version.
    agent-desktop-release = agentDesktopPackage;

    # Runs each host's real activation on fixture homes: T3 also writes these files from its UI.
    t3-settings-merge =
      pkgs.runCommand "t3-settings-merge"
        {
          nativeBuildInputs = [ pkgs.jq ];
          mbpActivation = mbpHome.home.activation.t3Settings.data;
          mbaActivation = mbaHome.home.activation.t3Settings.data;
          inherit (t3Fixtures) keybindings serverSettings clientSettings;
          expectedMbpKeybindings = t3Expected.mbpKeybindings;
          expectedMbpServerSettings = t3Expected.mbpServerSettings;
          expectedMbpClientSettings = t3Expected.mbpClientSettings;
          expectedMbpDesktopSettings = t3Expected.mbpDesktopSettings;
          expectedMbaKeybindings = t3Expected.mbaKeybindings;
        }
        ''
          set -euo pipefail
          activate() {
            local home="$1" activation="$2"
            (
              export HOME="$home"
              run() { "$@"; }
              eval "$activation"
            )
          }
          equals() {
            local file="$1" expected="$2"
            [ -f "$file" ] && [ ! -L "$file" ]
            jq -e --argjson expected "$expected" '. == $expected' "$file" >/dev/null || {
              echo "unexpected $file: $(cat "$file")" >&2
              exit 1
            }
          }

          mbp="$PWD/mbp/.t3/userdata"
          mkdir -p "$mbp"
          ln -s "$keybindings" "$mbp/keybindings.json"
          printf '%s' "$serverSettings" >"$mbp/settings.json"
          chmod 0600 "$mbp/settings.json"
          printf '%s' "$clientSettings" >"$mbp/client-settings.json"
          activate "$PWD/mbp" "$mbpActivation"
          equals "$mbp/keybindings.json" "$expectedMbpKeybindings"
          equals "$mbp/settings.json" "$expectedMbpServerSettings"
          equals "$mbp/client-settings.json" "$expectedMbpClientSettings"
          equals "$mbp/desktop-settings.json" "$expectedMbpDesktopSettings"
          cmp "$keybindings" ${t3Fixtures.keybindings}
          # The merge never widens a file's permissions; new files are private to the user.
          [ "$(stat -c %a "$mbp/settings.json")" = 600 ]
          [ "$(stat -c %a "$mbp/desktop-settings.json")" = 600 ]

          before=$(cat "$mbp"/*.json | sha256sum)
          activate "$PWD/mbp" "$mbpActivation"
          [ "$(cat "$mbp"/*.json | sha256sum)" = "$before" ]

          mba="$PWD/mba/.t3/userdata"
          mkdir -p "$mba"
          printf '%s' "$serverSettings" >"$mba/settings.json"
          printf '{not json' >"$mba/client-settings.json"
          activate "$PWD/mba" "$mbaActivation"
          [ "$(cat "$mba/settings.json")" = "$serverSettings" ]
          [ ! -e "$mba/desktop-settings.json" ]
          [ "$(cat "$mba/client-settings.json")" = '{not json' ]
          equals "$mba/keybindings.json" "$expectedMbaKeybindings"

          touch "$out"
        '';

    # macOS names the Dock and Cmd+Tab entry after the bundle of the running binary, so the
    # launcher must exec the Electron inside the T3 bundle with the llm-agents wrapper's environment.
    t3-desktop-app-bundle =
      pkgs.runCommand "t3-desktop-app-bundle"
        {
          nativeBuildInputs = [ pkgs.cctools ];
          app = "${t3DesktopPackage}/Applications/T3 Code (Beta).app";
          upstreamApp = "${t3Package.desktop}/Applications/T3 Code (Beta).app";
          upstreamLauncher = "${t3Package.desktop}/bin/t3code-desktop";
          unwrappedLauncher = "${t3Package.unwrapped.desktop}/bin/t3code-desktop";
          appDirectory = "${t3Package.unwrapped.desktop}/libexec/t3code/apps/desktop";
          signedCodex = lib.makeBinPath [ codexPackage ];
        }
        ''
          info() { /usr/bin/plutil -extract "$2" raw -o - "$1/Contents/Info.plist"; }
          wrapperPath() { strings "$1" | sed -n "s/^ *--prefix 'PATH' ':' '\(.*\)' .*$/\1/p"; }
          test "$(info "$app" CFBundleName)" = 'T3 Code (Beta)'
          test "$(info "$app" CFBundleDisplayName)" = 'T3 Code (Beta)'
          # Apple allows only letters, digits, "-" and "." in a bundle identifier.
          info "$app" CFBundleIdentifier | grep -qxE '[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+'
          info "$app" CFBundleIdentifier | grep -qF t3code
          cmp "$app/Contents/Resources/$(info "$app" CFBundleIconFile)" "$upstreamApp/Contents/Resources/t3code.icns"

          launcher="$app/Contents/MacOS/$(info "$app" CFBundleExecutable)"
          test -f "$launcher" && test -x "$launcher" && test ! -L "$launcher"
          strings "$launcher" | grep -qF "$app/Contents/MacOS/Electron"
          strings "$launcher" | grep -qF "$appDirectory"
          test -n "$(wrapperPath "$upstreamLauncher")"
          test "$(wrapperPath "$launcher")" = "$(wrapperPath "$upstreamLauncher")"
          wrapperPath "$launcher" | tr ':' '\n' | grep -qxF "$signedCodex"

          # Electron looks its helpers up as "Electron Helper*.app".
          test -x "$app/Contents/Frameworks/Electron Helper.app/Contents/MacOS/Electron Helper"
          upstreamElectron=$(strings "$unwrappedLauncher" | grep -m1 -oE '/nix/store/[^ ]*-electron-[^/ ]*/bin/electron')
          test "$(info "$app" CFBundleVersion)" = "$(info "''${upstreamElectron%/bin/electron}/Applications/Electron.app" CFBundleVersion)"

          /usr/bin/codesign --verify --deep --strict "$app"
          touch "$out"
        '';

    # Skills are generated by running the installed Darwin CLIs, so only a build proves the bundled text.
    automation-cli-skills =
      pkgs.runCommand "automation-cli-skills"
        {
          browserSkill = home.programs.agent-harness.skills.agent-browser;
          desktopSkill = home.programs.agent-harness.skills.agent-desktop;
        }
        ''
          grep -qx 'name: agent-browser' "$browserSkill/SKILL.md"
          grep -q 'agent-browser snapshot' "$browserSkill/SKILL.md"
          grep -qx 'name: agent-desktop' "$desktopSkill/SKILL.md"
          grep -q 'agent-desktop snapshot' "$desktopSkill/SKILL.md"
          # Only a plain single call escapes the sandbox, so the local rules must precede the upstream body.
          for skill in "$browserSkill" "$desktopSkill"; do
            awk '
              /^---$/ { fences++; next }
              fences == 2 && NF { print; exit }
            ' "$skill/SKILL.md" | grep -qx '## Local rules'
            grep -q 'one .* command per Bash call' "$skill/SKILL.md"
          done
          grep -q -- '--session <name>' "$browserSkill/SKILL.md"
          grep -q -- '--app <name>' "$desktopSkill/SKILL.md"
          touch "$out"
        '';
  };
}
