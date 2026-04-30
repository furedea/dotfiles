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
function command_not_found_handler() {
  if [[ -f "$1" ]]; then
    vi "$1"
  else
    echo "zsh: command not found: $1"
    return 127
  fi
}

DOTFILES="$HOME/ghq/github.com/furedea/dotfiles"

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
source "$XDG_CONFIG_HOME/zsh/nix-plugins.zsh"

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

# es: ship the last edited post (unwip with optional notice)
function es() {
  local notice_flag="--notice"

  case "$1" in
    "" )
      ;;
    -q | --quiet | --no-notice )
      notice_flag="--no-notice"
      shift
      ;;
    * )
      echo "usage: es [-q|--quiet]"
      return 1
      ;;
  esac

  [[ -n "$1" ]] && echo "usage: es [-q|--quiet]" && return 1
  [[ -z "$_ESA_LAST_POST" ]] && echo "es: no post to ship (edit something first)" && return 1
  kasa unwip -f "$notice_flag" "$_ESA_LAST_POST" && _ESA_LAST_POST=""
}

# gr: cd to git repository root
function gr() {
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "not in a git repo"; return 1 }
  builtin cd "$root"
}

# GitHub: create repo, clone into ghq root, apply template renames, run project setup
function ghcreate() {
  if [[ -z "$1" ]]; then
    cat >&2 <<'EOF'
usage: ghcreate <name> [gh repo create flags...]

  <name>: 'foo' (your account) or 'owner/foo' (explicit owner/org)
  Note: do not pass --clone; cloning is handled by ghq.
  For local-only, use: cd $(ghq create <name>)
EOF
    return 1
  fi

  local name="$1"; shift
  local short="${name##*/}" full owner

  if [[ "$name" == */* ]]; then
    full="$name"
  else
    owner=$(gh api user --jq .login) || return 1
    full="$owner/$short"
  fi

  echo "→ creating GitHub repo: $full"
  gh repo create "$name" "$@" || return 1

  echo "→ cloning into $(ghq root)/github.com/$full"
  ghq get "github.com/$full" || return 1
  builtin cd "$(ghq root)/github.com/$full" || return 1

  _ghcreate_apply_template "$short"

  "$DOTFILES/github/setup_repo.sh" "$full" || return 1
  [[ -f lefthook.yml ]] && command -v lefthook >/dev/null && lefthook install
}

# Helper: rewrite template-* placeholders to the new project name
function _ghcreate_apply_template() {
  local name="$1" file
  for file in pyproject.toml Cargo.toml; do
    [[ -f "$file" ]] && sed -i '' "s/^name = \"template-[a-z]*\"/name = \"$name\"/" "$file"
  done
  if [[ -f package.json ]] && command -v jq >/dev/null; then
    local tmp; tmp=$(mktemp)
    jq --arg n "$name" '.name = $n' package.json >"$tmp" && mv "$tmp" package.json
  fi
}

# Abbreviations: new shortcuts that don't shadow existing commands.
# Using -S (session scope) so definitions stay in this file, not in a separate file.
abbr --quiet -S lg="lazygit"
abbr --quiet -S gwt="git wt"
abbr --quiet -S ll="eza -la --git"
abbr --quiet -S lt="eza --tree --level=2"
abbr --quiet -S arm="exec arch -arch arm64e /bin/zsh --login"
abbr --quiet -S x64="exec arch -arch x86_64 /bin/zsh --login"
abbr --quiet -S ob="cd ~/Library/Mobile\ Documents/iCloud\~md\~obsidian/Documents/furedea"
abbr --quiet -S czg="npx --yes --package czg@1.13.0 --package @commitlint/config-conventional --call 'NODE_PATH=\"\$(dirname \"\$(dirname \"\$(command -v czg)\")\")\${NODE_PATH:+:\$NODE_PATH}\" czg'"

eval "$(zoxide init zsh --cmd j)"
eval "$(starship init zsh)"
eval "$(direnv hook zsh)"
eval "$(atuin init zsh --disable-up-arrow)"

# ghq + roots + fzf: Ctrl-G to fuzzy-cd into a managed repository, monorepo
# subproject, or worktree. `roots` expands each ghq path to all detected
# project markers (.git/config, go.mod, package.json, Cargo.toml).
function ghq-fzf() {
  local selected
  selected=$(ghq list -p | roots | fzf \
    --height=80% \
    --reverse \
    --preview "
      eza -la --git --icons --color=always {} 2>/dev/null | head -20
      echo
      echo '--- README ---'
      echo
      bat --color=always --style=plain --line-range=:80 \
        {}/README.md \
        {}/README.rst \
        {}/README \
        {}/README.txt \
        {}/readme.md \
        2>/dev/null || echo '(no README)'
    " \
    --preview-window=right:60%:wrap) || return
  BUFFER="builtin cd ${selected}"
  zle accept-line
  zle reset-prompt
}
zle -N ghq-fzf
bindkey '^G' ghq-fzf
