# Evaluate configuration contracts in Nix; executable integration remains in Bats.
{
  pkgs,
  lib,
  home,
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
  hister = mbp.launchd.user.agents.hister.serviceConfig;
  lsp = home.launchd.agents.lspmux;
  lspSettings =
    builtins.fromTOML
      home.home.file."Library/Application Support/lspmux/config.toml".text;
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
    pkgs.runCommand name { passthru = { inherit contracts; }; } ''
      touch "$out"
    '';
in
{
  home-configuration = check "home-configuration" {
    hooks-compose-herdr-and-moshi =
      builtins.attrNames home.programs.agent-harness.hooks == [
        "herdr"
        "moshi"
      ];
    github-stacked-pr-extension = names home.programs.gh.extensions == [ "gh-stack" ];
    neovim-nix-managed-plugin-loader = names home.programs.neovim.plugins == [ "lazy.nvim" ];
    yazi-bats-icon =
      (home.programs.yazi.theme.icon.prepend_exts or [ ]) == [
        {
          name = "bats";
          text = "";
        }
      ];
    ssh-identities-from-keychain =
      home.launchd.agents.ssh-agent-loader.config.ProgramArguments == [
        "/usr/bin/ssh-add"
        "--apple-load-keychain"
      ];
    ssh-identities-loaded-at-login = home.launchd.agents.ssh-agent-loader.config.RunAtLoad;
    ssh-client-config-unmanaged = !(home.home.file ? ".ssh/config");
    ssh-identity-creation-left-to-user = !(home.home.activation ? sshKeyGen);
    zsh-cache-after-startup-links = home.home.activation.zshCache.after == [ "linkGeneration" ];
    global-language-toolchains = hasAll [
      "python3"
      "uv"
      "nodejs"
      "pnpm"
      "cargo"
      "rustc"
      "clippy"
      "rustfmt"
    ] homeNames;
    no-mutable-language-installers =
      !(builtins.elem "rustup" homeNames)
      && !(home.home.activation ? rustupInit)
      && !(home.home.activation ? uvPythonInstall);
    managed-automation-python =
      toString home.xdg.configFile."dotfiles/bin/python3".source == lib.getExe pkgs.python314;
    agent-packages =
      builtins.filter (
        name:
        builtins.elem name [
          "claude-code"
          "codex"
          "devin-cli"
          "herdr"
        ]
      ) homeNames == [
        "herdr"
        "claude-code"
        "devin-cli"
        "codex"
      ];
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
    hermes-mutable-state-unmanaged = builtins.all (path: !(builtins.hasAttr path home.home.file)) [
      ".hermes/profiles/secretary/cron"
      ".hermes/profiles/secretary/state"
      ".hermes/profiles/secretary/.env"
      ".hermes/profiles/secretary/config.yaml"
    ];
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
    devin-smart-permission-mode =
      mbp.environment.variables.DEVIN_PERMISSION_MODE == "smart"
      && mba.environment.variables.DEVIN_PERMISSION_MODE == "smart";
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
      versions "moshi-hook" mbpHome.home.packages == [ "0.3.21" ]
      && lib.hasPrefix "/nix/store/" (toString mbpHome.home.file.".local/bin/moshi-hook".source)
      && lib.hasSuffix "/bin/moshi-hook" (toString mbpHome.home.file.".local/bin/moshi-hook".source);
    moshi-aqua = moshi.LimitLoadToSessionType == "Aqua";
    moshi-keychain-launcher =
      lib.hasSuffix "/bin/manage_moshi_hook" (builtins.head moshi.ProgramArguments)
      && builtins.tail moshi.ProgramArguments == [ "serve" ];
    moshi-keep-alive = moshi.KeepAlive;
    moshi-managed-runtime =
      lib.hasPrefix "/nix/store/" moshi.EnvironmentVariables.MOSHI_HOOK_BIN
      && lib.hasInfix "moshi-hook-0.3.21" moshi.EnvironmentVariables.MOSHI_HOOK_BIN
      && lib.hasSuffix "/bin/moshi-hook" moshi.EnvironmentVariables.MOSHI_HOOK_BIN;
    moshi-no-updater = !(mbpHome.launchd.agents ? moshi-hook-updater);
    moshi-no-environment-credentials = noSecrets moshi.EnvironmentVariables;
    moshi-only-on-mbp =
      builtins.filter (name: lib.hasPrefix "moshi-hook" name) (builtins.attrNames mbaHome.launchd.agents)
      == [ ];
    moshi-no-migration-hooks =
      builtins.filter (name: lib.hasPrefix "moshi" name) (builtins.attrNames mbpHome.home.activation)
      == [ ];
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
      (builtins.fromJSON (
        builtins.readFile mbaHome.home.file."Library/Preferences/hister/config.yml".source
      )).server.base_url == "https://mbp.tailbb556b.ts.net";
  };
}
