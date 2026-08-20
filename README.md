# dotfiles

Personal macOS configuration for an Apple Silicon Mac. Nix flakes compose
nix-darwin, Home Manager, Homebrew, editable dotfile symlinks, and the local AI
agent environment.

## Architecture

| Layer                  | Authority                                          | Responsibility                                                     |
| ---------------------- | -------------------------------------------------- | ------------------------------------------------------------------ |
| Flake composition      | [`flake.nix`](flake.nix)                           | Inputs, supported outputs, username, platform, and shared packages |
| macOS system           | [`nix/darwin/default.nix`](nix/darwin/default.nix) | System defaults, Homebrew, Nix settings, and privileged activation |
| User environment       | [`nix/home/default.nix`](nix/home/default.nix)     | CLI packages, Home Manager programs, symlinks, and user activation |
| Package overlays       | [`nix/overlays.nix`](nix/overlays.nix)             | Pinned packages not yet available from nixpkgs                     |
| Editable configuration | Top-level application directories                  | Files linked from this checkout into `$HOME`                       |

The primary outputs are:

- `darwinConfigurations.mbp`: the complete MacBook Pro configuration
- `darwinConfigurations.mba`: the complete MacBook Air configuration
- `homeConfigurations.kaito`: the user environment for faster iteration
- `packages.<system>.codex`: the pinned Codex CLI exposed by this flake
- `devShells.<system>.default`: commitlint and lefthook for repository work

The repository currently assumes:

- `aarch64-darwin`
- macOS user `kaito`
- checkout path `/Users/kaito/ghq/github.com/furedea/dotfiles`

The username and checkout path are defined together in [`flake.nix`](flake.nix).
Change them there before applying the configuration for another user or path.

## Bootstrap a New Mac

1. Install upstream Nix with flakes enabled:

    ```sh
    curl -sSfL https://artifacts.nixos.org/nix-installer | sh -s -- install --enable-flakes
    ```

2. Open a new shell and clone this repository at the configured path:

    ```sh
    git clone https://github.com/furedea/dotfiles \
      "$HOME/ghq/github.com/furedea/dotfiles"
    cd "$HOME/ghq/github.com/furedea/dotfiles"
    ```

3. Bootstrap nix-darwin with the output for the current Mac:

    ```sh
    # Use .#mba on the MacBook Air.
    sudo nix run \
      github:nix-darwin/nix-darwin/nix-darwin-25.11#darwin-rebuild \
      -- switch --flake .#mbp
    ```

The first switch installs the `darwin-rebuild` and `home-manager` commands used
for later updates.

## Apply Changes

Use the full switch to converge the actual Mac, including both nix-darwin and
its integrated Home Manager profile:

```sh
# Use #mba on the MacBook Air.
sudo darwin-rebuild switch --flake \
  "$HOME/ghq/github.com/furedea/dotfiles/#mbp"
```

For changes limited to [`nix/home/default.nix`](nix/home/default.nix), the
standalone Home Manager output provides a faster, unprivileged feedback loop:

```sh
home-manager switch --flake \
  "$HOME/ghq/github.com/furedea/dotfiles/#kaito"
```

The standalone and nix-darwin-integrated Home Manager outputs use different
profiles. A package removed with only `home-manager switch` may remain visible
from `/etc/profiles/per-user/kaito` until the next full `darwin-rebuild switch`.

Files managed with `mkOutOfStoreSymlink` update immediately when their source in
this checkout changes. Nix-generated files and Home Manager program settings
still require a switch.

## What Is Managed

### macOS and Homebrew

[`nix/darwin/default.nix`](nix/darwin/default.nix) manages:

- Nix flakes, weekly garbage collection, and Touch ID authentication for `sudo`
- keyboard, text input, Finder, Dock, trackpad, screenshots, lock screen, menu
  clock, Spotlight, and other macOS defaults
- Dock applications: Raycast, Arc, Obsidian, OrbStack, Slack, System Settings,
  and Nani
- display sleep disabled on both battery and charger
- Homebrew through nix-homebrew, with unlisted packages removed on activation

The current cask set is:

```text
arc                    bitwarden              chatgpt
deepl                  discord                firefox
font-jetbrains-mono    ghostty                google-chrome
homerow                karabiner-elements     mactex
microsoft-excel        microsoft-powerpoint   microsoft-word
nani                   obsidian               orbstack
raycast                skim                   slack
steam                  tailscale-app          vimr
```

The cask list in `nix/darwin/default.nix` is authoritative.

### User Environment

[`nix/home/default.nix`](nix/home/default.nix) installs and configures:

- shell and navigation tools including Zsh plugins, Starship, Atuin, direnv,
  zoxide, ghq, roots, git-wt, fzf, eza, bat, fd, ripgrep, and Yazi
- Git, Delta, GitHub CLI, Lazygit, Neovim, Tree-sitter, and Vim configuration
- Nix, Bash, Python, Rust, TypeScript, Lua, LaTeX, formatting, and linting tools
- Claude Code, Codex, OpenCode, and Herdr
- `programs.git`, `programs.delta`, `programs.gh`, `programs.lazygit`,
  `programs.direnv`, `programs.atuin`, `programs.agent-harness`, and
  `programs.yazi`

Activation also installs the stable Rust toolchain, installs the default Python
requested by uv, creates the SSH signing key when absent, and reconciles the
commit-pinned Herdr plugin set.

### AI Agent Environment

[agent-harness](https://github.com/furedea/agent-harness) owns the shared Claude
Code and Codex instructions, policies, hooks, skills, and generated files. This
repository builds release-matched Herdr and Moshi hook bundles, then passes them
through the module's generic `hooks.extra` boundary. Herdr comes from the pinned
flake input. Moshi Hook 0.2.87 is pinned in Nix for deterministic hook generation,
while the Homebrew installation remains the runtime daemon used by generated hooks.
Pairing tokens and mutable Moshi state are never added to the Nix store.

Herdr is pinned as a flake input and replaces tmux for local and managed remote
terminal sessions. The local configuration uses `ctrl+a` as its prefix and adds
popup commands for Yazi, Lazygit, a scratch shell, and the `reviewr` plugin.

Attach directly to a managed remote host with:

```sh
herdr --remote <ssh-target>
herdr --remote <ssh-target> --session <name>
```

The `persiyanov.reviewr` plugin revision is declared in
[`nix/home/default.nix`](nix/home/default.nix), synchronized during Home Manager
activation by [`herdr/sync_plugins.sh`](herdr/sync_plugins.sh), and justified by
[`ADR-0002`](docs/adr/0002_manage_herdr_plugins_through_home_manager_activation.md).

### Editable Symlinks

The following repository sources are linked directly into the home directory:

| Source                                       | Target                                 |
| -------------------------------------------- | -------------------------------------- |
| `zsh/.zshrc`, `zsh/.zshenv`, `zsh/.zprofile` | `~/.zshrc`, `~/.zshenv`, `~/.zprofile` |
| `bash/.bashrc`                               | `~/.bashrc`                            |
| `git/ignore`                                 | `~/.config/git/ignore`                 |
| `nvim/`                                      | `~/.config/nvim`                       |
| `vim/.vimrc`                                 | `~/.vimrc`                             |
| `starship/starship.toml`                     | `~/.config/starship.toml`              |
| `ghostty/config`                             | `~/.config/ghostty/config`             |
| `karabiner/karabiner.json`                   | `~/.config/karabiner/karabiner.json`   |
| `herdr/config.toml`, `herdr/reviewr.toml`    | Herdr config and reviewr plugin config |
| `dprint/dprint.json`                         | `~/dprint.json`                        |
| `prettier/.prettierrc`                       | `~/.prettierrc`                        |
| `.editorconfig`                              | `~/.editorconfig`                      |

Git, GitHub CLI, Lazygit, Atuin, Yazi, Zsh plugin paths, and agent-harness files
are generated from Home Manager modules rather than linked from similarly named
reference files.

### Reference and Export Files

These tracked files are not applied by Home Manager or nix-darwin:

- `atuin/config.toml`, `gh/config.yml`, `git/.gitconfig`, and the standalone
  `yazi/*.toml` files are reference copies; their active configuration comes
  from `nix/home/default.nix`
- `raycast/*.rayconfig` is a manual Raycast export
- `templates/` contains small files copied into other repositories as needed

## Repository Map

```text
.
├── flake.nix                  # Flake inputs and outputs
├── nix/                       # nix-darwin, Home Manager, and overlays
├── docs/adr/                  # Durable architecture decisions
├── zsh/ and bash/             # Interactive shell configuration
├── nvim/ and vim/             # Editor configuration
├── herdr/                     # Herdr UI and plugin synchronization
├── ghostty/                   # Terminal configuration
├── karabiner/                 # Keyboard remapping
├── starship/                  # Shell prompt
├── github/                    # Repository creation and policy scripts
├── tests/                     # Bats specifications by domain
├── dprint/ and prettier/      # Global formatter configuration
├── raycast/                   # Manual settings export
└── templates/                 # Manually copied reference templates
```

## Shell Behavior

The Zsh configuration:

- replaces common commands with modern equivalents such as `eza`, `bat`, `rg`,
  `fd`, and `dust`
- initializes zoxide, Starship, direnv, Atuin, and Nix-provided Zsh plugins
- provides `y` for Yazi directory changes and `gr` for the Git root
- binds `ctrl+g` to fuzzy repository and monorepo navigation through ghq, roots,
  and fzf
- provides editor-based esa helpers backed by the official esa CLI, with
  incremental WIP saves from Neovim

The Bash configuration provides the same core aliases and initializes zoxide,
Starship, and Atuin.

## Repository Automation

Create and clone a repository into the ghq root, then apply the standard
repository policy:

```sh
repo create <name-or-owner/name> (--public|--private|--internal) [options]
```

Common creation options include `--template`, `--description`, `--homepage`,
`--add-readme`, `--gitignore`, `--license`, `--disable-issues`,
`--disable-wiki`, and `--team`. Options that conflict with the managed ghq
clone destination (`--clone`, `--source`, `--push`, and `--remote`) are
rejected. Run `repo create --help` for details.

Apply the standard repository settings, vulnerability alerts, and ruleset to
an existing repository:

```sh
repo configure <name-or-owner/name>
```

A name without an owner defaults to the authenticated GitHub user. Run
`repo --help` or `repo -h` for the command overview. The commands are covered
by Bats tests under `tests/github/`.

## Formatting and Validation

Lefthook runs the pre-commit format and lint checks for changed files:

```sh
lefthook run pre-commit
```

Run the executable specifications directly with:

```sh
bats tests/github
bats tests/herdr
bats tests/esa
bats tests/nix
```

CI checks GitHub scripts with Bats and ShellCheck, checks Lua with Selene and
StyLua, checks Nix with Statix, deadnix, and nixfmt, checks JSON/TOML with
dprint, and lints prose with AutoCorrect. GitHub Actions are also checked with
actionlint, zizmor, and CodeQL.

dprint intentionally owns JSON and TOML only. Markdown is formatted with
prettierd because its four-space nested-list indentation matches the preferred
Obsidian style.

## Manual Setup

The repository cannot automate credentials or settings protected by macOS TCC.
After the first switch, configure as needed:

- sign in to GUI applications and iCloud
- run `gh auth login`
- run `esa auth login --scopes "read:post write:post"`
- configure Atuin synchronization credentials if history sync is wanted
- pair Moshi Hook with the iPhone app when restoring a host
- configure Night Shift, True Tone, display resolution, and Accessibility
  display options in System Settings
- import `raycast/*.rayconfig` when restoring Raycast manually

## Update Dependencies

Update every flake input, then apply the complete configuration:

```sh
nix flake update
# Use #mba on the MacBook Air.
sudo darwin-rebuild switch --flake \
  "$HOME/ghq/github.com/furedea/dotfiles/#mbp"
```

Update a single input when only one tool needs to move:

```sh
nix flake update codex-cli-nix
home-manager switch --flake \
  "$HOME/ghq/github.com/furedea/dotfiles/#kaito"
```
