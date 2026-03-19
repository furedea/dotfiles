{
  description = "furedea's dotfiles";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-25.11-darwin";
    nix-darwin.url = "github:nix-darwin/nix-darwin/nix-darwin-25.11";
    nix-darwin.inputs.nixpkgs.follows = "nixpkgs";
    home-manager.url = "github:nix-community/home-manager/release-25.11";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = inputs@{ self, nix-darwin, nixpkgs, home-manager }:
  let
    username = "kaito"; # ← change this when setting up on a new machine
  in {
    darwinConfigurations."mba" = nix-darwin.lib.darwinSystem {
      specialArgs = { inherit username; };
      modules = [
        ./nix/darwin/default.nix
        home-manager.darwinModules.home-manager
        {
          nixpkgs.config.allowUnfreePredicate = pkg:
            builtins.elem pkg.pname [ "zsh-abbr" "claude-code" "github-copilot-cli" ];

          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.backupFileExtension = "bak";
          home-manager.extraSpecialArgs = { inherit username; };

          home-manager.users.${username} = import ./nix/home/default.nix;
        }
      ];
    };
  };
}
