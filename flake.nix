{
  description = "furedea's dotfiles";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-26.05-darwin";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    nix-darwin.url = "github:nix-darwin/nix-darwin/nix-darwin-26.05";
    nix-darwin.inputs.nixpkgs.follows = "nixpkgs";
    home-manager.url = "github:nix-community/home-manager/release-26.05";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
    # Homebrew itself is left on the revision nix-homebrew pins. Overriding it
    # strands Homebrew behind homebrew-core, whose formulae always come from the
    # current API: brew 6.0.12 lacked the `symlink overwrite:` keyword and the
    # `bootstrap_cpython` install step, so post-install failed for openssl@3 and
    # python@3.11, and `brew install` then exited non-zero.
    nix-homebrew.url = "github:zhaofengli/nix-homebrew";
    llm-agents.url = "github:numtide/llm-agents.nix";
    agent-harness = {
      url = "github:furedea/agent-harness";
      inputs.home-manager.follows = "home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    agent-config = {
      url = "github:furedea/agent-config";
      inputs = {
        agent-harness.follows = "agent-harness";
        nixpkgs.follows = "nixpkgs";
        nixpkgs-unstable.follows = "nixpkgs-unstable";
      };
    };
    hister.url = "github:asciimoo/hister";
  };

  outputs =
    inputs@{
      self,
      nixpkgs,
      nixpkgs-unstable,
      nix-darwin,
      home-manager,
      nix-homebrew,
      llm-agents,
      agent-harness,
      agent-config,
      hister,
      ...
    }:
    let
      username = "kaito";
      system = "aarch64-darwin";
      dotfilesDir = "/Users/${username}/ghq/github.com/furedea/dotfiles";
      histerServerUrl = "https://mbp.tailbb556b.ts.net";
      allowUnfreePredicate =
        pkg:
        builtins.elem pkg.pname [
          "zsh-abbr"
          "claude-code"
          "moshi-hook"
          "1password-cli"
        ];
      pkgs = import nixpkgs {
        inherit system;
        config = { inherit allowUnfreePredicate; };
      };
      unstable = import nixpkgs-unstable {
        inherit system;
        config = { inherit allowUnfreePredicate; };
      };
      herdrPackage = llm-agents.packages.${system}.herdr;
      histerPackage = hister.packages.${system}.default;
      homeSpecialArgs = {
        inherit
          username
          dotfilesDir
          unstable
          llm-agents
          herdrPackage
          histerPackage
          histerServerUrl
          agent-harness
          agent-config
          system
          ;
      };
      hosts = {
        mba = {
          enableHisterService = false;
          enableMoshiService = false;
        };
        mbp = {
          enableHisterService = true;
          enableMoshiService = true;
        };
      };
      homeModules = [
        agent-harness.homeManagerModules.default
        ./nix/home/default.nix
      ];
      hostHomeSpecialArgs =
        { enableMoshiService, ... }: homeSpecialArgs // { inherit enableMoshiService; };
      mkDarwinConfiguration =
        host@{
          enableHisterService,
          enableMoshiService,
        }:
        nix-darwin.lib.darwinSystem {
          specialArgs = {
            inherit
              username
              enableHisterService
              enableMoshiService
              histerServerUrl
              agent-config
              ;
          };
          modules = [
            ./nix/darwin/default.nix
            hister.darwinModules.default
            nix-homebrew.darwinModules.nix-homebrew
            home-manager.darwinModules.home-manager
            {
              # Allowlist for packages with non-free licenses (nixpkgs blocks unfree by default).
              # Use allowUnfreePredicate instead of allowUnfree = true to avoid
              # accidentally permitting other proprietary packages.
              #   zsh-abbr         : CC-BY-NC-SA-4.0 + Hippocratic License v3.0 (both free=false)
              #   claude-code      : Anthropic proprietary (via numtide/llm-agents.nix)
              #   moshi-hook       : upstream binary release without a declared license
              #   1password-cli    : AgileBits proprietary CLI
              nixpkgs.config.allowUnfreePredicate = allowUnfreePredicate;

              home-manager = {
                useGlobalPkgs = true;
                useUserPackages = true;
                backupFileExtension = "bak";
                extraSpecialArgs = hostHomeSpecialArgs host;
                users.${username}.imports = homeModules;
              };
            }
          ];
        };
      # `runner` builds the trivial check derivations, so it must match the
      # system that builds them; `pkgs` only supplies Darwin package metadata.
      checkSetFor =
        runner:
        import ./nix/checks.nix {
          inherit pkgs inputs runner;
          inherit (nixpkgs) lib;
          home = self.homeConfigurations."${username}@mbp".config;
          inherit (self) homeConfigurations;
          darwin = self.darwinConfigurations;
        };
    in
    {
      # Evaluation checks run on both systems so Linux CI covers the Darwin
      # configurations; checks that build Darwin binaries stay on Darwin.
      checks = {
        ${system} = with checkSetFor pkgs; evaluation // darwinOnly;
        x86_64-linux = (checkSetFor nixpkgs.legacyPackages.x86_64-linux).evaluation;
      };

      darwinConfigurations = builtins.mapAttrs (_: mkDarwinConfiguration) hosts;

      # Home Manager picks `<user>@<hostname>` when `--flake` names no output.
      homeConfigurations = nixpkgs.lib.mapAttrs' (
        hostName: host:
        nixpkgs.lib.nameValuePair "${username}@${hostName}" (
          home-manager.lib.homeManagerConfiguration {
            inherit pkgs;
            extraSpecialArgs = hostHomeSpecialArgs host;
            modules = homeModules;
          }
        )
      ) hosts;

      # Dev shell for local work, consumed by direnv (`use flake`).
      devShells =
        nixpkgs.lib.genAttrs
          [
            "aarch64-darwin"
            "aarch64-linux"
            "x86_64-linux"
          ]
          (
            sys:
            let
              shellPkgs = nixpkgs.legacyPackages.${sys};
              shellUnstable = nixpkgs-unstable.legacyPackages.${sys};
            in
            {
              default = shellPkgs.mkShell {
                env = {
                  UV_PYTHON_DOWNLOADS = "never";
                  UV_PYTHON_PREFERENCE = "only-system";
                };
                packages = [
                  shellPkgs.actionlint
                  shellPkgs.bats
                  shellPkgs.commitlint
                  # lefthook before 2.1.6 runs hooks under a pty, which agent sandboxes deny.
                  shellUnstable.lefthook
                  # Same uv and Python as the Home Manager profile; Nix owns the interpreter, uv owns dependencies.
                  shellUnstable.uv
                  (shellPkgs.callPackage ./nix/packages/python_315.nix { })
                ]
                ++ import ./nix/lint_tools.nix {
                  pkgs = shellPkgs;
                  unstable = shellUnstable;
                };
              };
            }
          );
    };
}
