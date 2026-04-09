# Completion
autoload -Uz compinit
if [[ -n ~/.zcompdump(#qN.mh+24) ]]; then
    compinit
else
    compinit -C
fi

zstyle ":completion:*" format $'\e[2;37mCompleting %d\e[m'
zstyle ":completion:*" group-name ""
zstyle ":completion:*" list-colors "${(s.:.)LS_COLORS}"
export CARAPACE_BRIDGES='zsh,fish,bash,inshellisense'
source <(carapace _carapace)
setopt no_beep
setopt auto_pushd
setopt pushd_ignore_dups
setopt auto_cd
setopt hist_ignore_dups
setopt hist_ignore_all_dups
setopt hist_ignore_space
setopt hist_reduce_blanks
setopt share_history
setopt inc_append_history
setopt extended_glob
setopt interactive_comments
setopt correct
setopt glob_dots
setopt complete_in_word

export HISTSIZE=100000
export SAVEHIST=100000

# Command shadowing: replaces existing system commands with modern alternatives.
# Cannot use abbr here because zsh-abbr blocks abbreviations matching existing
# command names. alias is the correct tool for command shadowing.
alias ls="eza"
alias cat="bat --paging=never"
alias grep="rg"
alias find="fd"
alias du="dust"
alias cd="j"
alias vi="nvim"
alias vim="nvim"
alias view="nvim -R"
alias python3="python"

# yazi: change cwd on exit
function y() {
    local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
    yazi "$@" --cwd-file="$tmp"
    if cwd="$(command cat -- "$tmp")" && [ -n "$cwd" ] && [ "$cwd" != "$PWD" ]; then
        builtin cd -- "$cwd"
    fi
    rm -f -- "$tmp"
}

# Auto-open files with vi when command not found and file exists
command_not_found_handler() {
    if [[ -f "$1" ]]; then
        vi "$1"
    else
        echo "zsh: command not found: $1"
        return 127
    fi
}

export EDITOR="nvim"
export VISUAL="nvim"
export PATH="/usr/bin:$PATH"
export PATH="/opt/homebrew/bin:$PATH"
export XDG_CONFIG_HOME="$HOME/.config"
export PATH="/Library/TeX/texbin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export ESA_TEAM="posl"
export ESA_TOKEN=$(security find-generic-password -s "esa-token" -a "$USER" -w)

# Plugins
source "$HOME/.config/zsh/nix-plugins.zsh"

# esa helpers — always saves as WIP; use `es` to explicitly ship
_ESA_LAST_POST=""

# _esa_edit: open editor and remember post for `es`
function _esa_edit() {
    local post="$1"
    local editor="${EDITOR:-vim}"
    echo "editor: $editor"
    if EDITOR="$editor" kasa edit --no-notice "$post"; then
        _ESA_LAST_POST="$post"
    fi
}

# en: create new post under Members/k-shigyo/; errors if already exists (typo guard)
function en() {
    [[ -z "$1" ]] && echo "usage: en <title>" && return 1
    local url
    url=$(kasa touch --no-notice "Members/k-shigyo/$1") || return 1
    _esa_edit "$url"
}

# ee: edit post under Members/k-shigyo/ — direct name if arg given, fzf picker if no arg
function ee() {
    local post
    if [[ -n "$1" ]]; then
        post="Members/k-shigyo/$1"
    else
        post=$(kasa ls "Members/k-shigyo/" | awk '{print $NF}' | fzf --prompt="esa > ")
        [[ -z "$post" ]] && return
    fi
    kasa wip -f --no-notice "$post" >/dev/null 2>&1 || true
    _esa_edit "$post"
}

# eep: edit daily progress post; ensures WIP state before editing
function eep() {
    local post="議事録/2026年度配属/shigyo"
    kasa wip -f --no-notice "$post" >/dev/null 2>&1 || true
    _esa_edit "$post"
}

# es: ship the last edited post (unwip with notice)
function es() {
    [[ -z "$_ESA_LAST_POST" ]] && echo "es: no post to ship (edit something first)" && return 1
    kasa unwip -f --notice "$_ESA_LAST_POST" && _ESA_LAST_POST=""
}

# Abbreviations: new shortcuts that don't shadow existing commands.
# Using -S (session scope) so definitions stay in this file, not in a separate file.
abbr --quiet -S ll="eza -la --git"
abbr --quiet -S lt="eza --tree --level=2"
abbr --quiet -S arm="exec arch -arch arm64e /bin/zsh --login"
abbr --quiet -S x64="exec arch -arch x86_64 /bin/zsh --login"
abbr --quiet -S ob="cd ~/Library/Mobile\ Documents/iCloud\~md\~obsidian/Documents/furedea"

eval "$(zoxide init zsh --cmd j)"
eval "$(starship init zsh)"
eval "$(direnv hook zsh)"
eval "$(atuin init zsh --disable-up-arrow)"
