# Repair stale inherited PATH order and keep each entry only once.
typeset -U path PATH
# Homebrew and TeX remain fallbacks even when inherited ahead of /usr/bin.
path=("${(@)path:#/opt/homebrew/bin}")
path=("${(@)path:#/Library/TeX/texbin}")
path=(
  "$HOME/.nix-profile/bin"
  "/etc/profiles/per-user/$USER/bin"
  /run/current-system/sw/bin
  /nix/var/nix/profiles/default/bin
  "$HOME/.local/bin"
  "$HOME/.cargo/bin"
  "$HOME/.gem/bin"
  "${path[@]}"
  /opt/homebrew/bin
  /Library/TeX/texbin
)
# Enforced on every zsh start so stale inherited environments
# (e.g. a long-running herdr server snapshot) cannot override it.
export EDITOR=nvim
export VISUAL=nvim
