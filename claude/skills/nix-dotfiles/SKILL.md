---
name: nix-dotfiles
description: >
    Nix configuration reference for nix-darwin + home-manager on Apple Silicon macOS. ALWAYS load when the user says "dotfiles" — dotfiles here means nix-managed config. Load for: adding packages, configuring programs, dotfile symlinks, macOS system defaults, activation scripts, unfree packages, darwin-rebuild, home-manager switch, homebrew casks/brews, or any macOS app preference/shortcut change (app prefs like Homerow, Raycast, Ghostty are managed via system.defaults in nix/darwin/default.nix, NOT edited directly). Skip only for standalone non-.nix config files (karabiner.json, starship.toml, nvim/) needing no nix rebuild. Trigger on: "dotfiles", flake.nix, nix/home/default.nix, nix/darwin/default.nix, nixpkgs, home-manager, programs.*, homebrew.casks, homebrew.brews, mkOutOfStoreSymlink, allowUnfree, darwin-rebuild, system.defaults, "nix で管理", "add to nix", app shortcut/preference updates.
---

Read `INSTRUCTIONS.md` (in this skill's directory) for the full reference before proceeding.
