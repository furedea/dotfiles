---
name: nix-dotfiles
description: >
    Nix configuration reference for nix-darwin + home-manager on Apple Silicon macOS. ALWAYS load when the user says "dotfiles" in any context — dotfiles in this environment means nix-managed config. Load for: adding packages, configuring programs, dotfile symlinks, macOS system defaults, activation scripts, unfree packages, darwin-rebuild, or any macOS app preference/shortcut change (app preferences like Homerow, Raycast, Ghostty are managed via system.defaults in nix/darwin/default.nix, NOT edited directly). Do NOT load only when editing a truly standalone config file (karabiner.json, starship.toml, nvim/) that is explicitly NOT a .nix file and requires no nix rebuild. Trigger on: "dotfiles", flake.nix, nix/home/default.nix, nix/darwin/default.nix, nixpkgs, home-manager, programs.*, homebrew.casks, homebrew.brews, mkOutOfStoreSymlink, allowUnfree, darwin-rebuild, system.defaults, "nix で管理", "add to nix", any app shortcut/preference update request.
---

Read `INSTRUCTIONS.md` (in this skill's directory) for the full reference before proceeding.
