# Preserve inherited tool precedence and keep each entry only once.
typeset -U path PATH
(( ${path[(Ie)$HOME/.local/bin]} )) || path+=("$HOME/.local/bin")
(( ${path[(Ie)$HOME/.cargo/bin]} )) || path+=("$HOME/.cargo/bin")
(( ${path[(Ie)$HOME/.gem/bin]} )) || path+=("$HOME/.gem/bin")
# Enforced on every zsh start so stale inherited environments
# (e.g. a long-running herdr server snapshot) cannot override it.
export EDITOR=nvim
export VISUAL=nvim
