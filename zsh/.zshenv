# Keep the Nix profile order supplied by nix-darwin and remove inherited duplicates.
typeset -U path PATH
path+=("$HOME/.gem/bin" "$HOME/.cargo/bin")
# Enforced on every zsh start so stale inherited environments
# (e.g. a long-running herdr server snapshot) cannot override it.
export EDITOR=nvim
export VISUAL=nvim
