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
    brew-src = {
      url = "github:Homebrew/brew/0bfbbb6c1a08254177d133f5c14a8f506ea7888e";
      flake = false;
    };
    nix-homebrew.inputs.brew-src.follows = "brew-src";
    llm-agents.url = "github:numtide/llm-agents.nix";
    hermes-agent.url = "github:NousResearch/hermes-agent";
    nix-openclaw-tools = {
      url = "github:openclaw/nix-openclaw-tools";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    apple-mail-cli = {
      url = "github:furedea/apple-mail-cli";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    agent-harness = {
      url = "github:furedea/agent-harness";
      inputs.home-manager.follows = "home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    hister.url = "github:asciimoo/hister";
  };

  outputs =
    {
      nixpkgs,
      nixpkgs-unstable,
      nix-darwin,
      home-manager,
      nix-homebrew,
      llm-agents,
      hermes-agent,
      nix-openclaw-tools,
      apple-mail-cli,
      agent-harness,
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
      hermesAgentPackage = hermes-agent.packages.${system}.minimal;
      gogCliPackage = nix-openclaw-tools.packages.${system}.gogcli;
      appleMailCliPackage = apple-mail-cli.packages.${system}.default;
      histerPackage = hister.packages.${system}.default;
      homeSpecialArgs = {
        inherit
          username
          dotfilesDir
          unstable
          llm-agents
          appleMailCliPackage
          gogCliPackage
          hermesAgentPackage
          herdrPackage
          histerPackage
          histerServerUrl
          agent-harness
          system
          ;
      };
      mkDarwinConfiguration =
        {
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
              nixpkgs.config.allowUnfreePredicate = allowUnfreePredicate;

              home-manager = {
                useGlobalPkgs = true;
                useUserPackages = true;
                backupFileExtension = "bak";
                extraSpecialArgs = homeSpecialArgs // {
                  inherit enableMoshiService;
                };
                users.${username} = {
                  imports = [
                    agent-harness.homeManagerModules.default
                    ./nix/home/default.nix
                  ];
                };
              };
            }
          ];
        };
    in
    {
      darwinConfigurations = {
        mba = mkDarwinConfiguration {
          enableHisterService = false;
          enableMoshiService = false;
        };
        mbp = mkDarwinConfiguration {
          enableHisterService = true;
          enableMoshiService = true;
        };
      };

      homeConfigurations.${username} = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = homeSpecialArgs // {
          enableMoshiService = false;
        };
        modules = [
          agent-harness.homeManagerModules.default
          ./nix/home/default.nix
        ];
      };

      # Re-export codex CLI per system so local users can `nix shell .#codex`
      # without hard-coding the upstream flake URL. Versions stay pinned via
      # flake.lock.
      packages =
        nixpkgs.lib.genAttrs
          [
            "aarch64-darwin"
            "x86_64-darwin"
            "aarch64-linux"
            "x86_64-linux"
          ]
          (sys: {
            inherit (llm-agents.packages.${sys}) codex;
          });

      # Dev shell for local work, consumed by direnv (`use flake`).
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
            in
            {
              default = shellPkgs.mkShell {
                packages = with shellPkgs; [
                  commitlint
                  lefthook
                ];
              };
            }
          );
    };
}
