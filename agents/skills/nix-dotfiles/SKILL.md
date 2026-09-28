---
name: nix-dotfiles
description: >
    Use when deciding where or how to change and apply Nix-managed packages, program settings,
    dotfile links, or macOS preferences on this Apple Silicon nix-darwin/home-manager system.
---

# Nix Configuration — Dotfiles Reference

## Scope

This dotfiles repository uses Nix-managed configuration. Edit declared macOS preferences and
shortcuts through `system.defaults` or the owning activation script in `nix/darwin/default.nix`.
Application dotfiles such as `ghostty/config`, `karabiner/karabiner.json`, `starship/starship.toml`,
and `nvim/` need this reference only when their Nix ownership or rebuild requirements are relevant.

## Architecture

```
~/ghq/github.com/furedea/dotfiles/
├── flake.nix                        # entry point: inputs + outputs
│   ├── darwinConfigurations         # host-specific full systems (mba / mbp)
│   └── homeConfigurations."kaito"   # standalone home-manager (no sudo)
├── nix/darwin/default.nix           # system layer (nix-darwin)
│   ├── system.defaults.*            # macOS settings
│   ├── homebrew.*                   # GUI apps, taps, MAS
│   ├── nix-homebrew                 # homebrew installation via nix
│   └── system.activationScripts     # root-level activation scripts
└── nix/home/default.nix             # user layer (home-manager)
    ├── home.packages                # CLI tools from nixpkgs / unstable / flake inputs
    ├── programs.*                   # declarative program configs, including agent-harness
    ├── home.file.*                  # editable links and Nix-generated files
    └── home.activation              # post-activation hooks for mutable runtime state
```

Platform: `aarch64-darwin` (Apple Silicon). Read `flake.nix` for release channels and package-set
wiring; `unstable` is the separately imported `nixpkgs-unstable` package set.

## Flake Inputs

Use `flake.nix` for input names and URLs, and `flake.lock` for pinned revisions. Claude Code,
Codex, and Herdr packages come from `llm-agents`; `agent-harness` renders and deploys the personal
source under `agents/`. Inspect package selection and wrappers in `nix/home/default.nix` before
changing an agent package.

`homeSpecialArgs` in `flake.nix` passes inputs and selected packages to Home Manager through
`extraSpecialArgs`. Follow that wiring when adding a third-party package.

## Rebuild Commands

Two build paths exist — pick the right one for the change being made.

### `darwin-rebuild switch` (full system)

```bash
sudo darwin-rebuild switch --flake "$HOME/ghq/github.com/furedea/dotfiles/#<host>"
```

Rebuilds **both** nix-darwin (system.defaults, homebrew, activationScripts) and home-manager (packages, programs, dotfile symlinks). Requires `sudo` because nix-darwin writes to `/etc/` and `/Library/Preferences/`. Use this for:

- Changes to `nix/darwin/default.nix` (macOS defaults, homebrew casks/brews, activation scripts)
- Changes to `flake.nix` (inputs, overlays, unfree list)
- Any change that touches both layers

Replace `<host>` with the target machine's `mba` or `mbp` configuration. Host-specific service
flags are defined in `flake.nix`; preserve the target host's selection.

### `home-manager switch` (user only, no sudo)

```bash
home-manager switch --flake "$HOME/ghq/github.com/furedea/dotfiles/#kaito"
```

Rebuilds **only** home-manager (packages, programs, dotfile symlinks, activation hooks). Does not touch nix-darwin or require `sudo`. Use this for:

- Changes to `nix/home/default.nix` only (adding packages, editing programs.\*, updating dotfile symlinks, activation hooks)
- Changes to the managed agent source under `agents/`
- Faster iteration when the darwin layer is unchanged

The `homeConfigurations."kaito"` output in `flake.nix` imports `nix/home/default.nix` directly.
It has its own service flags. Use the matching full-system configuration when host-specific
services must be preserved.

### When symlinked dotfiles change

Changes to files linked via `mkOutOfStoreSymlink` (e.g. `.zshrc`, `starship.toml`, `nvim/`) take effect immediately — no rebuild needed. The symlink points to the working tree, not the nix store.

### When managed agent source changes

Edit `agents/` in this repository. `agentSource` in `nix/home/default.nix` snapshots that directory
into the Nix store and patches executable shebangs before `programs.agent-harness` renders and
deploys it. Changes to instructions, skills, hooks, policies, and provider settings require a
rebuild and activation through the appropriate path above. Generated files in `~/.claude/` and
`~/.codex/` are deployment outputs. See `docs/adr/0016_own_personal_agent_source.md` and
`docs/adr/0027_let_nix_own_python_entry_points.md` for the ownership and deployment rationale.

## Where to Add a Package

| What                              | Where                                                   | Example                                     |
| --------------------------------- | ------------------------------------------------------- | ------------------------------------------- |
| CLI tool in nixpkgs stable        | `nix/home/default.nix` → `home.packages`                | `bat`, `ripgrep`                            |
| CLI tool only in unstable         | `nix/home/default.nix` → `home.packages`                | `unstable.atuin`, `unstable.oxfmt`          |
| Tool from a flake input           | `nix/home/default.nix` → `home.packages`                | `llm-agents.packages.${system}.claude-code` |
| Global fallback language runtime  | `nix/home/default.nix` → `home.packages`                | `python314`, `rustc`, `nodejs_24`           |
| GUI app (macOS .app)              | `nix/darwin/default.nix` → `homebrew.casks`             | `"obsidian"`, `"arc"`                       |
| Mac App Store app                 | `nix/darwin/default.nix` → `homebrew.masApps`           | `LINE = 539883307`                          |
| Homebrew formula (not in nixpkgs) | `nix/darwin/default.nix` → `homebrew.brews`             | `"winebarrel/kasa/kasa"`                    |
| Homebrew tap                      | `nix/darwin/default.nix` → `homebrew.taps`              | `"winebarrel/kasa"`                         |
| System-wide tool (before login)   | `nix/darwin/default.nix` → `environment.systemPackages` | `pkgs.vim`                                  |

### Package organization in home.packages

Follow the category comments in `nix/home/default.nix` → `home.packages`. That definition owns the
current package inventory and grouping.

## Allowing Unfree Packages

The `allowUnfreePredicate` in `flake.nix` owns the accepted package names and is shared across the
package sets and Darwin configuration. To add a new unfree package, determine its `pname` from the
selected package source, then update that predicate.

## Configuring Programs (home-manager modules)

Read `nix/home/default.nix` → `programs` for enabled modules and their settings. Herdr is configured
through its package, linked configuration, and activation hook in that file.

Shell initialization is maintained in the linked `zsh/.zshrc`. Check both that file and the owning
program module before adding an integration; keep initialization in one place. Existing direnv
and Atuin modules disable generated Zsh integration for this reason.

## Dotfile Symlinks

Read `home.file` and `xdg.configFile` in `nix/home/default.nix` for each target's source.
Entries using the `link` helper (`mkOutOfStoreSymlink`) point at editable working-tree files;
use it for frequently edited files, since changes apply without a rebuild. Use a generated
`.text` file only when its content depends on Nix store paths. Agent deployment follows the
managed-source lifecycle above.

## Activation Hooks

Use activation commands when the target is inherently mutable and cannot be represented by a
package or managed file.

Read `nix/home/default.nix` → `home.activation` for current workflows and their ordering. In
particular, SSH identity creation is interactive; activation checks the identity and provides
operator instructions when it is missing or unprotected.

- Install language runtimes through `home.packages`; do not download them with activation hooks.
- Use `${pkgs.xxx}/bin/xxx` to reference the exact Nix store binary.
- Suppress failures with `|| true` only when the operation is explicitly non-fatal.
- Follow the existing DAG dependencies. Hooks that consume freshly linked files use
  `entryAfter [ "linkGeneration" ]`.

## macOS System Defaults (nix-darwin)

Read `nix/darwin/default.nix` → `system.defaults` for the managed categories and current values.

For keys not covered by native nix-darwin options, use `system.defaults.CustomUserPreferences."com.bundle.id"`.

## System Activation Scripts

Read `nix/darwin/default.nix` → `system.activationScripts` for root-level work and any operations
that require the primary user's context. Preserve those execution boundaries when editing a script.

## Homebrew (via nix-homebrew)

Read `nix-homebrew` and `homebrew` in `nix/darwin/default.nix` for the current settings and
lists. `onActivation.cleanup = "uninstall"` uninstalls any cask or brew removed from those lists
on the next `darwin-rebuild switch`, so remove an app by deleting its entry.
