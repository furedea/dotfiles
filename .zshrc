zstyle ":completion:*:commands" rehash 1
setopt no_beep
setopt auto_pushd
setopt pushd_ignore_dups
setopt auto_cd
setopt hist_ignore_dups
setopt share_history
setopt inc_append_history

export HISTSIZE=100000
export SAVEHIST=100000

alias arm="exec arch -arch arm64e /bin/zsh --login"
alias x64="exec arch -arch x86_64 /bin/zsh --login"
alias vi="nvim"
alias vim="nvim"
alias view="nvim -R"
alias python3="python"
alias docker-login='(){ docker exec -it $1 bash -lc "su - $2" }'

source "$HOME/.rye/env"

export PATH="/usr/bin:$PATH"

export PATH="/opt/homebrew/bin:$PATH"

export MODULAR_HOME="$HOME/.modular"
export PATH="$MODULAR_HOME/pkg/packages.modular.com_mojo/bin:$PATH"

export PATH="$PATH":"$HOME/fvm/default/bin"
export PATH="$PATH":"$HOME/.pub-cache/bin"
export XDG_CONFIG_HOME="$HOME/.config"
## [Completion]
## Completion scripts setup. Remove the following line to uninstall
[[ -f /Users/kaito/.dart-cli-completion/zsh-config.zsh ]] && . /Users/kaito/.dart-cli-completion/zsh-config.zsh || true
## [/Completion]
