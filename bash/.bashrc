# PATH / env vars
export PATH="/opt/homebrew/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.gem/bin:$PATH"
export EDITOR="nvim"
export VISUAL="nvim"
export XDG_CONFIG_HOME="$HOME/.config"

# Cargo
[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"

# Homebrew
eval "$(/opt/homebrew/bin/brew shellenv)"

# Tool initializations (bash)
eval "$(mise activate bash)"
eval "$(zoxide init bash --cmd j)"
eval "$(starship init bash)"
eval "$(atuin init bash --disable-up-arrow)"

# Aliases
alias vi="nvim"
alias vim="nvim"
alias view="nvim -R"
alias ls="eza"
alias ll="eza -la --git"
alias lt="eza --tree --level=2"
alias cat="bat --paging=never"
alias grep="rg"
alias find="fd"
alias du="dust"
alias cd="j"
