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
    codex-cli-nix.url = "github:sadjow/codex-cli-nix";
    nix-claude-code.url = "github:ryoppippi/nix-claude-code";
    agent-harness = {
      url = "github:furedea/agent-harness";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      nixpkgs-unstable,
      nix-darwin,
      home-manager,
      nix-homebrew,
      codex-cli-nix,
      nix-claude-code,
      agent-harness,
      ...
    }:
    let
      username = "kaito";
      system = "aarch64-darwin";
      dotfilesDir = "/Users/${username}/ghq/github.com/furedea/dotfiles";
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
                  agent-harness
                  system
                  ;
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

      homeConfigurations.${username} = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = {
          inherit
            username
            dotfilesDir
            unstable
            nix-claude-code
            codex-cli-nix
            agent-harness
            system
            ;
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
            codex = codex-cli-nix.packages.${sys}.default;
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
