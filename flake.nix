{
  description = "furedea's dotfiles";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-25.11-darwin";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    nix-darwin.url = "github:nix-darwin/nix-darwin/nix-darwin-25.11";
    nix-darwin.inputs.nixpkgs.follows = "nixpkgs";
    home-manager.url = "github:nix-community/home-manager/release-25.11";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
    nix-homebrew.url = "github:zhaofengli/nix-homebrew";
    nix-claude-code.url = "github:ryoppippi/nix-claude-code";
    codex-cli-nix.url = "github:sadjow/codex-cli-nix";
  };

  outputs =
    {
      nix-darwin,
      nixpkgs,
      nixpkgs-unstable,
      home-manager,
      nix-homebrew,
      nix-claude-code,
      codex-cli-nix,
      ...
    }:
    let
      username = "kaito";
      system = "aarch64-darwin";
      dotfilesDir = "/Users/${username}/ghq/github.com/furedea/dotfiles";
      agentPaths = import ./nix/agents/paths.nix {
        inherit (nixpkgs) lib;
        inherit username dotfilesDir;
      };
      allowUnfreePredicate =
        pkg:
        builtins.elem pkg.pname [
          "zsh-abbr"
          "claude"
          "github-copilot-cli"
        ];
      pkgs = import nixpkgs {
        inherit system;
        config = { inherit allowUnfreePredicate; };
        overlays = import ./nix/overlays.nix;
      };
      unstable = import nixpkgs-unstable {
        inherit system;
        config = { inherit allowUnfreePredicate; };
      };
    in
    {
      darwinConfigurations."mba" = nix-darwin.lib.darwinSystem {
        specialArgs = { inherit username; };
        modules = [
          ./nix/darwin/default.nix
          nix-homebrew.darwinModules.nix-homebrew
          home-manager.darwinModules.home-manager
          {
            # Allowlist for packages with non-free licenses (nixpkgs blocks unfree by default).
            # Use allowUnfreePredicate instead of allowUnfree = true to avoid
            # accidentally permitting other proprietary packages.
            #   zsh-abbr         : CC-BY-NC-SA-4.0 + Hippocratic License v3.0 (both free=false)
            #   claude           : Anthropic proprietary (via ryoppippi/nix-claude-code)
            #   github-copilot-cli: GitHub proprietary
            nixpkgs.config.allowUnfreePredicate = allowUnfreePredicate;

            home-manager = {
              useGlobalPkgs = true;
              useUserPackages = true;
              backupFileExtension = "bak";
              extraSpecialArgs = {
                inherit
                  username
                  dotfilesDir
                  unstable
                  nix-claude-code
                  codex-cli-nix
                  system
                  ;
              };
              users.${username} = import ./nix/home/default.nix;
            };
          }
        ];
      };

      homeConfigurations.${username} = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = {
          inherit
            username
            dotfilesDir
            unstable
            nix-claude-code
            codex-cli-nix
            system
            ;
        };
        modules = [
          ./nix/home/default.nix
        ];
      };

      # Re-export codex CLI and python3 per system so CI (and local users)
      # can `nix shell .#codex` / `nix build .#python3` without hard-coding
      # upstream flake URLs. Versions stay pinned via flake.lock.
      packages =
        nixpkgs.lib.genAttrs
          [
            "aarch64-darwin"
            "x86_64-darwin"
            "aarch64-linux"
            "x86_64-linux"
          ]
          (sys: {
            codex = codex-cli-nix.packages.${sys}.default;
            inherit (nixpkgs.legacyPackages.${sys}) python3;
          });

      # Dev shells for everyday Python work and for CI-equivalent hook tests.
      # The default shell is consumed by direnv (`use flake`); hook-tests keeps
      # formatter/linter dependencies explicit so Bats does not depend on the
      # caller's global PATH.
      devShells =
        nixpkgs.lib.genAttrs
          [
            "aarch64-darwin"
            "x86_64-darwin"
            "aarch64-linux"
            "x86_64-linux"
          ]
          (
            sys:
            let
              shellPkgs = nixpkgs.legacyPackages.${sys};
              shellUnstable = import nixpkgs-unstable {
                system = sys;
                config = { inherit allowUnfreePredicate; };
              };
            in
            {
              default = shellPkgs.mkShell {
                packages = with shellPkgs; [
                  commitlint
                  lefthook
                  uv
                ];

                env = {
                  UV_MANAGED_PYTHON = "1";
                };

                shellHook = ''
                  if [ -d .venv/bin ]; then
                    export PATH="$PWD/.venv/bin:$PATH"
                  fi
                '';
              };

              hook-tests = shellPkgs.mkShell {
                packages = [
                  codex-cli-nix.packages.${sys}.default
                  shellPkgs.bats
                  shellPkgs.dprint
                  shellPkgs.git
                  shellPkgs.jq
                  shellPkgs.oxlint
                  shellPkgs.ripgrep
                  shellPkgs.ruff
                  shellPkgs.rustfmt
                  shellPkgs.shellcheck
                  shellPkgs.shfmt
                  shellUnstable.oxfmt
                ];
              };
            }
          );

      # Pure data outputs consumed by bats tests. Going through the flake (and
      # flake.lock) keeps tests reproducible: no `<nixpkgs>` channel lookup,
      # no `--impure`, and the same nixpkgs revision as the dev environment.
      lib =
        let
          libSet = nixpkgs.lib;
          agentSettings = import ./nix/agents/claude_settings.nix {
            lib = libSet;
            inherit username dotfilesDir;
          };
          codexSettings = import ./nix/agents/codex_settings.nix {
            lib = libSet;
            inherit username dotfilesDir;
          };
          agentHooks = import ./nix/agents/hooks.nix { };
          agentPolicy = import ./nix/agents/command_policy.nix { lib = libSet; };
          agentSkills = import ./nix/agents/skills.nix { };
        in
        {
          inherit (agentPaths) dotfilesHomePath;
          inherit (agentSettings) generatedSettings;
          inherit (agentPolicy) codexRules forbiddenRulesJson;
          inherit (agentHooks) codexHooks;
          codexFilesystemPermissions = codexSettings.filesystemPermissions;
          codexConfigFragmentToml = codexSettings.configFragmentToml;
          agentSkillOverrides = agentSkills.overrides;
          policyRules = map (entry: { inherit (entry) decision pattern; }) agentPolicy.rules;
        };
    };
}
