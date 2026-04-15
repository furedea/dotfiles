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
  };

  outputs =
    inputs@{
      self,
      nix-darwin,
      nixpkgs,
      nixpkgs-unstable,
      home-manager,
      nix-homebrew,
    }:
    let
      username = "kaito";
      system = "aarch64-apple-darwin";
      allowUnfreePredicate =
        pkg:
        builtins.elem pkg.pname [
          "zsh-abbr"
          "claude-code"
          "github-copilot-cli"
        ];
      pkgs = import nixpkgs {
        inherit system;
        config = { inherit allowUnfreePredicate; };
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
            #   claude-code      : Anthropic proprietary
            #   github-copilot-cli: GitHub proprietary
            nixpkgs.config.allowUnfreePredicate = allowUnfreePredicate;

            home-manager = {
              useGlobalPkgs = true;
              useUserPackages = true;
              backupFileExtension = "bak";
              extraSpecialArgs = { inherit username unstable; };
              users.${username} = import ./nix/home/default.nix;
            };
          }
        ];
      };

      homeConfigurations.${username} = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = { inherit username unstable; };
        modules = [
          ./nix/home/default.nix
        ];
      };
    };
}
