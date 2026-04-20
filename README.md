# dotfiles

furedea's macOS dotfiles — managed with [Nix](https://nixos.org/), [nix-darwin](https://github.com/nix-darwin/nix-darwin), and [home-manager](https://github.com/nix-community/home-manager).

## Overview

| Layer | Tool | Role |
| --- | --- | --- |
| System settings | nix-darwin | macOS defaults, Homebrew, activation scripts |
| User environment | home-manager | CLI tools, shell, git, editor config |
| Dotfiles | symlinks (`mkOutOfStoreSymlink`) | Direct editable files in this repo |
| Language toolchains | Nix / rustup / uv | Node.js + pnpm + ni / Rust / Python |

## Requirements

- macOS (Apple Silicon)
- macOS username must be **`kaito`** (hardcoded in `nix/darwin/default.nix` and `nix/home/default.nix`). If different, update the following before running:
    - `flake.nix` — `home-manager.users.<name>`
    - `nix/darwin/default.nix` — `users.users.<name>.home`, `system.primaryUser`
    - `nix/home/default.nix` — `home.username`, `home.homeDirectory`

## Setup (new Mac)

1. Install Nix using the [NixOS nix-installer](https://github.com/NixOS/nix-installer). The `--enable-flakes` flag turns on the `nix-command` and `flakes` experimental features so nix-darwin can be bootstrapped without extra arguments below:

    ```sh
    curl -sSfL https://artifacts.nixos.org/nix-installer | sh -s -- install --enable-flakes
    ```

    After the installer finishes, open a new shell so `nix` is on `PATH`.

2. Clone dotfiles:

    ```sh
    git clone https://github.com/furedea/dotfiles ~/dotfiles
    ```

3. Bootstrap nix-darwin:

    ```sh
    sudo nix run nix-darwin -- switch --flake "$HOME/dotfiles#mba"
    ```

> **Do not use the Determinate Systems installer** (`install.determinate.systems/nix`). Despite sharing a Rust codebase with the NixOS nix-installer above, current versions install Determinate Nix by default, whose `determinate-nixd` daemon conflicts with nix-darwin's native Nix management (`nix.settings`, `nix.gc`). If you need to recover from this, run `/nix/nix-installer uninstall` and reinstall using the command in step 1.

> Subsequent system updates use `darwin-rebuild` directly (installed by the step above):
>
> ```sh
> sudo darwin-rebuild switch --flake "$HOME/dotfiles#mba"
> ```
>
> For user-environment updates only, use `home-manager` directly:
>
> ```sh
> home-manager switch --flake "$HOME/dotfiles#kaito"
> ```
>
> `home-manager` CLI itself is installed by this config, so if it is not yet available on PATH, run one `darwin-rebuild switch` first.

`darwin-rebuild switch` automatically:

- Installs all CLI tools via Nix
- Installs GUI apps via Homebrew Cask
- Applies all macOS system settings
- Generates `~/.config/zsh/nix-plugins.zsh` (zsh plugin paths)
- Runs `rustup toolchain install stable`, `uv python install`
- Symlinks dotfiles from this repo to `~`

## Directory Structure

```
dotfiles/
├── flake.nix                  # Entry point — inputs and outputs
├── nix/
│   ├── darwin/default.nix     # nix-darwin: system settings, Homebrew, activation scripts
│   └── home/default.nix       # home-manager: packages, programs, symlinks
├── zsh/
│   ├── .zshrc
│   ├── .zshenv
│   └── .zprofile
├── nvim/                      # Neovim config (lazy.nvim)
├── ghostty/                   # Ghostty terminal config
├── tmux/                      # tmux config (via home-manager programs.tmux)
├── starship/                  # Starship prompt config
├── git/                       # Global gitignore
├── karabiner/                 # Karabiner-Elements key mapping
├── atuin/                     # Shell history (via home-manager programs.atuin)
├── yazi/                      # File manager (via home-manager programs.yazi)
├── jj/                        # Jujutsu VCS root-level config
├── claude/                    # Claude Code config (agents, hooks, skills, etc.)
└── ...
```

## What nix-darwin Manages

### CLI Tools (Nix packages)

| Category | Tools |
| --- | --- |
| Shell | bash-language-server, bats, carapace, shellcheck, shfmt, zoxide, zsh-abbr, zsh-autosuggestions, zsh-fast-syntax-highlighting |
| File ops | bat, dust, eza, fd, fzf, ripgrep |
| Dev | just, neovim, starship, tree-sitter |
| CI | actionlint |
| Formatters | autocorrect, dprint, prettierd (markdown only — see [note](#markdown-formatter)) |
| VCS | git (programs.git), delta, jujutsu, gh |
| Language runtimes | nodejs, pnpm, ni, rustup (Rust), uv (Python) |
| AI / CLI | claude-code, codex |
| macOS | xcodes, dotenvx, marp-cli |

### GUI Apps (Homebrew Cask)

appcleaner, arc, bitwarden, chatgpt, claude, cmux, discord, firefox, font-jetbrains-mono, ghostty, google-chrome, karabiner-elements, mactex, nani, obsidian, orbstack, raycast, slack, steam, vimr, visual-studio-code, zoom

### Mac App Store

LINE is installed manually via the App Store app. Automated `masApps` management is not used because Apple hardened `installd` on macOS 15.7.2+ (CVE-2025-43411 mitigation), which makes `mas install` unable to run under the `sudo darwin-rebuild` root context — see [mas-cli#1221](https://github.com/mas-cli/mas/issues/1221).

### macOS System Settings

| Category | Settings |
| --- | --- |
| Keyboard | KeyRepeat=2, InitialKeyRepeat=15, F1-F12 as function keys |
| Text input | All auto-corrections disabled (caps, spelling, quotes, dashes, period) |
| Appearance | Dark mode, always show extensions, always show scroll bars |
| Trackpad | Tap to click, right-click, momentum scroll, pinch, rotate, Force Click |
| Trackpad speed | 3.0 (fastest) |
| Mouse speed | 3 (fastest) |
| Finder | Show hidden files, path bar, status bar, column view, folders first |
| Dock | Auto-hide, bottom, size 128, no recents, minimize to app icon |
| Hot corners | TL=Desktop, TR=Notification Center, BL=Lock Screen, BR=Quick Note |
| Dock apps | cmux, Raycast, Arc, Obsidian, OrbStack, Slack, Discord, LINE, System Settings, Nani |
| Screenshot | Save to ~/Pictures as file |
| Lock screen | Require password immediately after sleep |
| Menu bar clock | 24h, seconds, date, day of week |
| Stage Manager | Disabled |
| iCloud default save | Disabled (save locally by default) |
| .DS_Store on network | Disabled |
| Spotlight | Disabled (use Raycast instead) |
| Apple Music auto-launch | Disabled |
| Display sleep | 5 min on battery / never on charger |
| Software Update | Auto-download and auto-install disabled |
| Timezone | Asia/Tokyo |

### Dotfile Symlink Strategy

Files that are frequently edited (shell config, Neovim, etc.) are symlinked directly from this repo using `mkOutOfStoreSymlink`. Editing the file in `~/dotfiles/` takes effect immediately without running `darwin-rebuild`.

Files generated by Nix (e.g. zsh plugin paths) are written as `home.file.*.text` so Nix expands Nix store paths at evaluation time.

| File/Dir | Strategy |
| --- | --- |
| `.zshrc`, `.zshenv`, `.zprofile` | symlink → `zsh/` |
| `.config/nvim` | symlink → `nvim/` |
| `.config/ghostty/config` | symlink → `ghostty/` |
| `.config/starship.toml` | symlink → `starship/` |
| `.config/karabiner/karabiner.json` | symlink → `karabiner/` |
| `.config/zsh/nix-plugins.zsh` | generated by Nix (zsh plugin source paths) |
| `programs.tmux` | fully managed by home-manager |
| `programs.git` | fully managed by home-manager |
| `programs.atuin` | fully managed by home-manager |
| `programs.yazi` | fully managed by home-manager |

### Reference Copies (not symlinked)

Some directories are kept as **plain copies for backup/reference** only. They are not symlinked into `~` and are not applied automatically by `darwin-rebuild`.

| Dir | Source | Notes |
| --- | --- | --- |
| `kawasemi4/` | `~/Library/Mobile Documents/com~apple~CloudDocs/Kawasemi4/` | Kawasemi4 key settings and dictionary. Synced via iCloud on new Mac; copy here is for version control backup. Update manually when settings change. |
| `templates/` | — | Project starter templates (Cargo.toml, pyproject.toml, etc.). Copy manually to new projects as needed. |

## Markdown Formatter

`dprint-plugin-markdown` hardcodes list indent to 2 spaces (CommonMark minimum) with no configuration option. `prettierd` is used instead with `tabWidth: 4` in `~/.prettierrc` to get 4-space list nesting matching Obsidian.

> **TODO:** switch back to dprint once [dprint-plugin-markdown#176](https://github.com/dprint/dprint-plugin-markdown/pull/176) merges.

## GitHub Actions Workflow Linting

`actionlint` is installed via Nix and integrated with Neovim through `nvim-lint`. It only runs for files under `.github/workflows/*.yml` and `.github/workflows/*.yaml` by assigning those paths the compound filetype `yaml.ghaction`.

## GitHub Workflow Starters

Starter workflows for commonly used GitHub automation and security checks live in `templates/github/`.

Included templates:

- `templates/github/.github/workflows/gha_hygiene.yml`
    - `actionlint` + `zizmor`
- `templates/github/.github/workflows/dependency_review.yml`
    - Dependency Review for pull requests
- `templates/github/.github/workflows/codeql.yml`
    - CodeQL advanced setup starter
- `templates/github/.github/workflows/release_please.yml`
    - Release Please starter

GitHub-native features such as Renovate, Push Protection, Secret Scanning, and Rulesets are documented in `templates/github/README.md` instead of being stored as workflow files.

## Post-rebuild Checklist

Run these after `darwin-rebuild switch` if needed.

Update dprint plugin checksums (first time only, or after changing plugin versions):

```sh
dprint config update
```

## Manual Setup (after darwin-rebuild)

These settings cannot be automated:

| Setting | Where |
| --- | --- |
| Night Shift | System Settings > Displays > Night Shift |
| True Tone | System Settings > Displays > True Tone |
| Display resolution | `brew install displayplacer && displayplacer list` → update activation script |
| Accessibility (reduceMotion/Transparency) | System Settings > Accessibility > Display |
| Input Sources (Kawasemi4) | System Settings > Keyboard > Input Sources |
| Kawasemi4 settings | Kawasemi4 app preferences |
| iCloud sign-in | System Settings > Apple ID (syncs user dict, Focus, etc.) |
| Touch ID | System Settings > Touch ID |
| Apple Pay | System Settings > Wallet & Apple Pay |
| Wi-Fi / Bluetooth | System Settings > Wi-Fi / Bluetooth |
| Notifications (per-app) | System Settings > Notifications |

## Update

Update all packages and apply system + user changes:

```sh
sudo darwin-rebuild switch --flake "$HOME/dotfiles#mba"
```

Update user packages and home-manager config only:

```sh
home-manager switch --flake "$HOME/dotfiles#kaito"
```

Update Codex CLI from codex-cli-nix, then apply only home-manager changes:

```sh
nix flake update codex-cli-nix
home-manager switch --flake "$HOME/dotfiles#kaito"
```
