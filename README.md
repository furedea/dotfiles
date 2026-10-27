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
| Local Nix packages     | [`nix/packages/`](nix/packages/)                   | Local derivations and narrowly scoped package overrides            |
| Editable configuration | Top-level application directories                  | Files linked from this checkout into `$HOME`                       |

The primary outputs are:

- `darwinConfigurations.mbp`: the complete MacBook Pro configuration
- `darwinConfigurations.mba`: the complete MacBook Air configuration
- `homeConfigurations."kaito@mbp"` and `homeConfigurations."kaito@mba"`: each
  host's user environment for faster iteration
- `devShells.<system>.default`: commitlint and lefthook for repository work

The repository currently assumes:

- `aarch64-darwin`
- macOS user `kaito`
- checkout path `~/ghq/github.com/furedea/dotfiles`

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
      github:nix-darwin/nix-darwin/nix-darwin-26.05#darwin-rebuild \
      -- switch --flake .#mbp
    ```

The first switch installs the `darwin-rebuild` and `home-manager` commands used
for later updates.

### Bootstrap a Linux Server without Nix

Servers without Nix or root access use the bootstrap script in
[furedea/agent-config](https://github.com/furedea/agent-config#bootstrap-a-linux-server-without-nix).

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
  "$HOME/ghq/github.com/furedea/dotfiles/#kaito@mbp"
```

Each `kaito@<host>` output enables the same host-specific services as the
matching `darwinConfigurations` host. Use `kaito@mba` on the MacBook Air.

Run `:Lazy update` in Neovim to update editor plugins and commit the resulting
`nvim/lazy-lock.json` change.

The standalone and nix-darwin-integrated Home Manager outputs use different
profiles. A package removed with only `home-manager switch` may remain visible
from `/etc/profiles/per-user/kaito` until the next full `darwin-rebuild switch`.

Files managed with `mkOutOfStoreSymlink` update immediately when their source in
this checkout changes. Nix-generated files and Home Manager program settings
still require a switch.

### Rust Language Server

Start Neovim from each project's direnv-enabled shell. Rust connections use
[lspmux](https://codeberg.org/p2502/lspmux); other language servers start directly.
Home Manager manages its LaunchAgent and native macOS configuration under
`~/Library/Application Support/lspmux/`. Inspect the service with `lspmux config`,
`lspmux status --json`, or `~/Library/Logs/lspmux.log`.

The global analyzer is independent of rustup. Keep `rust-analyzer` out of project
dev shells; provide the project's compiler, Cargo, Clippy, and Rust sources there.
The environment allowlist in [`nix/home/default.nix`](nix/home/default.nix) forwards
toolchain and native build settings from Neovim. Add project-specific build
variables there when needed; arbitrary environment variables are not forwarded.
Changing directories inside an existing Neovim does not run the shell's direnv
hook. Open another Neovim from the other project's shell when toolchains differ.

The daemon reuses an analyzer when its workspace, executable, arguments, and
forwarded environment match. After the last client disconnects, the analyzer
remains until the configured idle timeout and the next garbage collection check.
The daemon itself remains available. Restart Neovim from a refreshed shell after
changing a toolchain or build environment. LSP multi-folder workspaces are not
supported by lspmux 0.3.0; Cargo workspace members can share their Cargo root.
If only configuration files change and the forwarded environment stays identical,
wait for the old instance to expire or restart the service before reconnecting.

## What Is Managed

### macOS and Homebrew

[`nix/darwin/default.nix`](nix/darwin/default.nix) manages:

- Nix flakes, weekly garbage collection, and Touch ID authentication for `sudo`
- keyboard, text input, Finder, Dock, trackpad, screenshots, lock screen, menu
  clock, Spotlight, and other macOS defaults
- Dock applications: Tinycast, Ghostty, Dia, Obsidian, OrbStack, Slack,
  System Settings, and Nani
- display sleep disabled on both battery and charger
- Homebrew through nix-homebrew, with unlisted packages removed on activation

The current cask set is:

```text
chatgpt                deepl
discord                firefox                font-jetbrains-mono
ghostty                google-chrome         homerow
karabiner-elements     mactex                microsoft-excel
microsoft-powerpoint   microsoft-word        nani
obsidian               orbstack              skim
slack                  steam                  tailscale-app
thebrowsercompany-dia  tinycast              vimr
```

The cask list in `nix/darwin/default.nix` is authoritative.

### User Environment

[`nix/home/default.nix`](nix/home/default.nix) installs and configures:

- shell and navigation tools including Zsh plugins, Starship, Atuin, direnv,
  zoxide, ghq, roots, git-wt, fzf, eza, bat, fd, ripgrep, and Yazi
- Git, Delta, GitHub CLI, Lazygit, Neovim, Tree-sitter, and Vim configuration
- Nix, Bash, Python, Rust, TypeScript, Lua, LaTeX, formatting, and linting tools
- Claude Code, Codex, Devin, Hermes Agent, pi, and Herdr
- `programs.git`, `programs.delta`, `programs.gh`, `programs.lazygit`,
  `programs.direnv`, `programs.atuin`, `programs.agent-harness`, and
  `programs.yazi`

Activation also creates the Hermes secretary profile when absent, rebuilds the
Zsh completion cache, reports how to create or protect the SSH signing key when
it is missing or has no passphrase, and reconciles the commit-pinned Herdr plugin
set.

### AI Agent Environment

The [agent-config](https://github.com/furedea/agent-config) repository owns the personal
cross-provider agent source: instructions, policies, hooks, skills, and provider settings for Claude Code,
Codex, Devin, Hermes Agent, and pi. The
[agent-harness](https://github.com/furedea/agent-harness) flake renders and deploys
that source for each provider. This repository also builds release-matched Herdr
and Moshi hook bundles and composes them through the module's generic `hooks`
boundary. Herdr comes from the pinned flake input. Moshi Hook is pinned in
[`nix/packages/moshi_hook.nix`](nix/packages/moshi_hook.nix); on the MacBook Pro, a
Home Manager LaunchAgent runs that same binary as the daemon used by generated hooks.
Pairing tokens and mutable Moshi state are never added to the Nix store.

Servers without Nix use the bootstrap script in agent-config instead of the Home
Manager module; it still reads host-specific settings from `~/.config/dotfiles/`.
Verification state, hook decisions, and the other behavior of the source are
documented in agent-config's README and
[ADRs](https://github.com/furedea/agent-config/tree/main/docs/adr), such as
[ADR-0012](https://github.com/furedea/agent-config/blob/main/docs/adr/0012_keep_the_personal_agent_source_in_its_own_repository.md).

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
activation by [`herdr/plugin_sync.py`](herdr/plugin_sync.py), and justified by
[`ADR-0002`](docs/adr/0002_manage_herdr_plugins_through_home_manager_activation.md).

#### Development Cycle

The development cycle, its constraints, and where to open a session are documented
in agent-config's [DESIGN](https://github.com/furedea/agent-config/blob/main/docs/DESIGN.md)
and [CONTRIBUTING](https://github.com/furedea/agent-config/blob/main/CONTRIBUTING.md).
After merging dotfiles changes, run `darwin-rebuild switch` on `main`.

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

Git, GitHub CLI, Lazygit, Atuin, Yazi, Zsh plugin paths, and rendered agent files
are generated from Home Manager modules rather than linked from similarly named
reference files.

### Reference and Export Files

These tracked files are not applied by Home Manager or nix-darwin:

- [`templates/`](templates/README.md) contains reference files copied into other repositories,
  including a complete release workflow with project-specific build steps

## Repository Map

```text
.
├── flake.nix                  # Flake inputs and outputs
├── nix/                       # nix-darwin, Home Manager, and local packages
├── docs/adr/                  # Durable architecture decisions
├── zsh/ and bash/             # Interactive shell configuration
├── nvim/ and vim/             # Editor configuration
├── herdr/                     # Herdr UI and plugin synchronization
├── hermes/                    # Editable Hermes secretary profile sources
├── scripts/                   # Shell launchers for Git signing, Hister, and Moshi
├── .agents/                   # Repository rules for the agent harness hooks
├── ghostty/                   # Terminal configuration
├── karabiner/                 # Keyboard remapping
├── starship/                  # Shell prompt
├── github/                    # Repository creation and policy scripts
├── tests/                     # Python contracts and Bats integration by domain
├── dprint/ and prettier/      # Global formatter configuration
├── tinycast/                 # Manual settings export
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
by Python unit and CLI integration tests under `tests/github/`.

## Formatting and Validation

Automation logic uses Python's standard library, without runtime pip packages.
The project environment supplies development tools such as pytest, Ruff, and ty.
Nix pins the interpreter in deployed hook and statusline shebangs; the server
bootstrap in agent-config pins them to its uv-managed interpreter. The `repo` and
Herdr launchers use Nix's fixed Python with editable source files. Python entry points use isolated mode to ignore project import paths.
For development or CI, run a source command with `python3 -I -B path/to/command.py`.
The Zsh esa helper still uses `$XDG_CONFIG_HOME/dotfiles/bin/python3` (`~/.config`
when unset), because it updates parent-shell state. See
[ADR-0027](docs/adr/0027_let_nix_own_python_entry_points.md) for the deployment rationale.

Python tests cover policy decisions, test selection, structured output, CLI and
provider payloads, subprocess failures, disposable Git state, and configuration
contracts. Bats checks shell, editor, and Nix-managed launcher integration.
Declarative Home Manager and host contracts also have native flake checks in
`nix/checks.nix`.
Hermes gateway tests run on macOS with the Nix-built Hermes Python environment;
they do not add Hermes dependencies to the dotfiles Python environment.

Tests are grouped by the feature they verify, not by implementation language.
Python and Bats tests live together under directories such as `tests/herdr/`
and `tests/hermes/`. Agent hook and skill tests live with their source in
[furedea/agent-config](https://github.com/furedea/agent-config). `tests/nix/` bridges the
repository-wide native configuration checks, including the Home Manager rendering of the
agent source and the repository's related-test mapping.
Shared pytest fixtures live in `tests/conftest.py` and importable test support in
`tests/runtime.py`.

The verification hook is documented in agent-config's
[DESIGN](https://github.com/furedea/agent-config/blob/main/docs/DESIGN.md#verification).
pytest spreads tests across all CPU cores through pytest-xdist by default; pass
`-n 0` when a debugging option such as `-s` or `--pdb` needs a single process.

Lefthook runs the pre-commit format and lint checks for changed files:

```sh
lefthook run pre-commit
```

Run the executable specifications directly with:

```sh
bats --recursive tests
uv run --frozen pytest
nix flake check
```

CI checks shell integration with Bats and checks Python automation with Ruff, ty,
and pytest. Tests marked `integration` run in the Bats job; other pytest tests run
separately without duplicating those cases.
CI checks all tracked `.sh` files with ShellCheck and shfmt, failing if no scripts
are selected. Zsh files are not passed to these Bash checks. CI checks Lua with
Selene and StyLua, checks Nix with Statix, deadnix, and nixfmt, checks JSON/TOML
with dprint, and lints prose with AutoCorrect. GitHub Actions are also checked
with actionlint, zizmor, and CodeQL.

dprint intentionally owns JSON and TOML only. Markdown is formatted with
prettierd because its four-space nested-list indentation matches the preferred
Obsidian style.

## Manual Setup

The repository cannot automate credentials or settings protected by macOS TCC.
After the first switch, configure as needed:

- sign in to GUI applications and iCloud
- create the SSH signing key with a passphrase, using the commands the Home Manager
  activation prints, and store the passphrase in the macOS Keychain
- run `gh auth login`
- run `esa auth login --scopes "read:post write:post"`
- configure Atuin synchronization credentials if history sync is wanted
- on MacBook Pro, generate a Hister access token and copy it to the clipboard:

    ```sh
    /usr/bin/openssl rand -hex 32 | /usr/bin/pbcopy
    ```

- on MacBook Pro, save that token in the login Keychain without placing it in
  shell history or a process argument; paste it at the password prompt:

    ```sh
    /usr/bin/security add-generic-password \
      -U \
      -a "$USER" \
      -s "org.furedea.hister.access-token" \
      -w
    ```

- apply the `mbp` nix-darwin configuration; its Hister LaunchAgent reads the
  token from Keychain at runtime and refuses to start when the item is absent
- on MacBook Pro, publish Hister to the tailnet and inspect the resulting route:

    ```sh
    tailscale serve --bg --yes 4433
    tailscale serve status
    ```

- install the Hister browser extension on both Macs, set its server URL to
  `https://mbp.tailbb556b.ts.net/`, and paste the same access token into its
  authentication setting
- retrieve the token for extension enrollment or rotation without printing it:

    ```sh
    /usr/bin/security find-generic-password \
      -a "$USER" \
      -s "org.furedea.hister.access-token" \
      -w | /usr/bin/pbcopy
    ```

- clear the clipboard after enrolling both extensions:

    ```sh
    printf '' | /usr/bin/pbcopy
    ```

- pair Moshi Hook with the iPhone app when restoring a host
- configure Night Shift, True Tone, display resolution, and Accessibility
  display options in System Settings
- import `tinycast/*` when restoring Tinycast manually

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
nix flake update llm-agents
# Use #kaito@mba on the MacBook Air.
home-manager switch --flake \
  "$HOME/ghq/github.com/furedea/dotfiles/#kaito@mbp"
```
