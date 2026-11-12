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
  codexWrapperText =
    (builtins.head (builtins.filter (package: (package.name or "") == "codex") home.home.packages))
    .text;
  hister = mbp.launchd.user.agents.hister.serviceConfig;
  lsp = home.launchd.agents.lspmux;
  lspSettings =
    builtins.fromTOML
      home.home.file."Library/Application Support/lspmux/config.toml".text;
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
            "claude-code"
            "codex"
            "herdr"
          ]
        ) homeNames == [
          "herdr"
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
