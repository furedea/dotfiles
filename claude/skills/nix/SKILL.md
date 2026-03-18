---
name: nix
description: >
  Nix configuration reference for nix-darwin + home-manager on Apple Silicon macOS.
  ALWAYS load when the user says "dotfiles" in any context — dotfiles in this environment
  means nix-managed config. Load for: adding packages, configuring programs, dotfile
  symlinks, macOS system defaults, activation scripts, unfree packages, darwin-rebuild,
  or any macOS app preference/shortcut change (app preferences like Homerow, Raycast,
  Ghostty are managed via system.defaults in nix/darwin/default.nix, NOT edited directly).
  Do NOT load only when editing a truly standalone config file (karabiner.json,
  starship.toml, nvim/) that is explicitly NOT a .nix file and requires no nix rebuild.
  Trigger on: "dotfiles", flake.nix, nix/home/default.nix,
  nix/darwin/default.nix, nixpkgs, home-manager, programs.*, homebrew.casks,
  homebrew.brews, mkOutOfStoreSymlink, allowUnfree, darwin-rebuild, system.defaults,
  "nixで管理", "add to nix", any app shortcut/preference update request.
---

# Nix Configuration — Dotfiles Reference

## Architecture

```
flake.nix                          # entry point: inputs + outputs
├── nix/darwin/default.nix         # system layer (nix-darwin)
│   ├── system.defaults.*          # macOS settings
│   ├── homebrew.*                 # GUI apps, taps, MAS
│   └── system.activationScripts  # run-once shell scripts
└── nix/home/default.nix           # user layer (home-manager)
    ├── home.packages              # CLI tools from nixpkgs
    ├── programs.*                 # declarative program configs
    ├── home.file.*                # dotfile symlinks / generated files
    └── home.activation            # post-activation hooks
```

Platform: `aarch64-darwin` (Apple Silicon). Release channel: `25.11` for all inputs.

## Rebuild Command

```bash
sudo darwin-rebuild switch --flake "$HOME/dotfiles#mba"
```

Run this after every edit to `flake.nix`, `nix/darwin/default.nix`, or `nix/home/default.nix`.
Changes to symlinked dotfiles (e.g. `.zshrc`, `starship.toml`) take effect immediately — no rebuild needed.

## Where to Add a Package

| What | Where | Example |
|------|-------|---------|
| CLI tool available in nixpkgs | `nix/home/default.nix` → `home.packages` | `bat`, `ripgrep` |
| GUI app (macOS .app) | `nix/darwin/default.nix` → `homebrew.casks` | `"obsidian"` |
| Homebrew tap formula | `nix/darwin/default.nix` → `homebrew.brews` | `"dmmulroy/tap/jj-starship"` |
| Mac App Store app | `nix/darwin/default.nix` → `homebrew.masApps` | `LINE = 539883307` |
| System-wide tool (available before login) | `nix/darwin/default.nix` → `environment.systemPackages` | `pkgs.vim` |

### Adding a CLI package

```nix
# nix/home/default.nix — home.packages
home.packages = with pkgs; [
  bat
  ripgrep
  your-new-tool   # ← add here
];
```

### Adding a GUI app (cask)

```nix
# nix/darwin/default.nix — homebrew.casks
casks = [
  "arc"
  "your-new-app"   # ← add here
];
```

## Allowing Unfree Packages

Add the package's `pname` to `nixpkgs.config.allowUnfreePredicate` in `flake.nix`:

```nix
# flake.nix
nixpkgs.config.allowUnfreePredicate = pkg:
  builtins.elem pkg.pname [ "zsh-abbr" "claude-code" "your-unfree-pkg" ];
```

To find a package's `pname`, run: `nix eval nixpkgs#your-pkg.pname`

## Configuring Programs (home-manager modules)

```nix
# nix/home/default.nix
programs.some-tool = {
  enable = true;
  enableZshIntegration = false; # .zshrc is a dotfile symlink — integrate manually
  settings = {
    key = "value";
  };
};
```

> **Why `enableZshIntegration = false`?** `.zshrc` is a `mkOutOfStoreSymlink` dotfile managed
> directly in the repo. Auto-injected lines would conflict. Add shell integration manually in
> `zsh/.zshrc` using `eval "$(tool init zsh)"` or source the generated file.

## Dotfile Symlinks

### Editable symlinks (changes apply immediately, no rebuild)

```nix
# nix/home/default.nix
let
  dotfiles = "${config.home.homeDirectory}/dotfiles";
  link = path: config.lib.file.mkOutOfStoreSymlink "${dotfiles}/${path}";
in
{
  home.file = {
    ".zshrc".source         = link "zsh/.zshrc";
    ".config/starship.toml".source = link "starship/starship.toml";
    ".config/nvim".source   = link "nvim";        # directory symlink
  };
}
```

Use `mkOutOfStoreSymlink` for files you edit frequently (shell configs, editor configs).

### Nix-generated files (content defined in Nix, read-only)

```nix
home.file.".config/zsh/nix-plugins.zsh".text = ''
  source ${pkgs.zsh-autosuggestions}/share/zsh-autosuggestions/zsh-autosuggestions.zsh
'';
```

Use `.text` when the file content depends on Nix store paths (e.g. plugin source paths).

## Activation Hooks

Run commands after home-manager writes files (e.g. install language toolchains):

```nix
# nix/home/default.nix
home.activation = {
  myHook = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    ${pkgs.mise}/bin/mise install --quiet 2>/dev/null || true
  '';
};
```

- Use `${pkgs.xxx}/bin/xxx` to reference the exact Nix store binary.
- Always end with `|| true` to prevent rebuild failures from non-fatal errors.
- `entryAfter [ "writeBoundary" ]` ensures dotfiles are written before this hook runs.

## macOS System Defaults (nix-darwin)

```nix
# nix/darwin/default.nix
system.defaults = {
  NSGlobalDomain.KeyRepeat = 2;
  finder.AppleShowAllFiles = true;
  dock.autohide = true;

  # For keys not covered by native nix-darwin options:
  CustomUserPreferences = {
    "com.apple.dock" = {
      "some-key" = true;
    };
  };
};
```

Common namespaces: `NSGlobalDomain`, `finder`, `dock`, `trackpad`, `screencapture`,
`screensaver`, `menuExtraClock`, `WindowManager`.

## Activation Scripts (system-level)

For actions that need to run as root or affect `/Library/Preferences`:

```nix
# nix/darwin/default.nix
system.activationScripts.postActivation.text = ''
  defaults write /Library/Preferences/com.example.app SomeKey -bool true
'';
```

## Key Patterns in This Repo

| Pattern | Usage |
|---------|-------|
| `with pkgs;` | Avoids repeating `pkgs.` inside `home.packages = with pkgs; [ ... ]` |
| `link "path"` | Helper defined in `let` block for `mkOutOfStoreSymlink` |
| `${pkgs.xxx}` in `.text` | Embeds Nix store paths into generated shell files |
| `enableZshIntegration = false` | All programs with shell integration, because `.zshrc` is a symlink |
| `|| true` in activation | Prevents non-fatal errors from aborting the rebuild |
