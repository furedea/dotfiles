#!/bin/sh
# Claude Code statusline - 2 lines with powerline-style ANSI segments.
# Reads JSON from stdin, outputs ANSI-colored text to stdout.

set -eu

JQ=$(command -v jq)   || { echo "jq not found" >&2; exit 1; }
JJ=$(command -v jj)   || JJ=""
GIT=$(command -v git)  || GIT=""

# --- Color config (fg only, no background) ---
FG_CWD=14       # bold cyan  (Starship directory default)
FG_VCS=10       # bold green (Starship custom module default)
FG_MODEL=111    # soft blue
FG_CTX=252      # light gray
FG_5H=217       # soft rose
FG_7D=116       # soft teal
FG_SEP=240      # dim separator
FG_BAR_HI=76    # green  (remaining >= 50%)
FG_BAR_MD=220   # yellow (remaining 20-49%)
FG_BAR_LO=203   # red    (remaining < 20%)

SEP=" │ "

# --- Helpers ---
seg() {
    # seg <fg> <text>
    printf '\033[1;38;5;%dm%s\033[0m' "$1" "$2"
}

sep() {
    printf '\033[38;5;%dm%s\033[0m' "$FG_SEP" "$SEP"
}

make_bar() {
    # make_bar <used_pct> <width>
    # Filled blocks represent consumed capacity; more fill = less headroom.
    _pct="$1"
    _width="${2:-4}"
    _units=$(( _pct * _width * 8 / 100 ))
    _full=$(( _units / 8 ))
    _partial=$(( _units % 8 ))

    if [ "$_pct" -ge 80 ]; then _bar_fg="$FG_BAR_LO"
    elif [ "$_pct" -ge 50 ]; then _bar_fg="$FG_BAR_MD"
    else _bar_fg="$FG_BAR_HI"
    fi

    _bar=""
    _i=0
    while [ "$_i" -lt "$_full" ]; do _bar="${_bar}█"; _i=$(( _i + 1 )); done
    case "$_partial" in
        1) _bar="${_bar}▏" ;; 2) _bar="${_bar}▎" ;; 3) _bar="${_bar}▍" ;;
        4) _bar="${_bar}▌" ;; 5) _bar="${_bar}▋" ;; 6) _bar="${_bar}▊" ;;
        7) _bar="${_bar}▉" ;;
    esac
    [ "$_partial" -gt 0 ] && _i=$(( _i + 1 ))
    while [ "$_i" -lt "$_width" ]; do _bar="${_bar}░"; _i=$(( _i + 1 )); done

    printf '\033[38;5;%dm%s\033[0m' "$_bar_fg" "$_bar"
}

fmt_duration() {
    # fmt_duration <seconds>
    # Output: "Xd Yh" or "Xh Ym" or "Xm"
    _s="$1"
    _days=$(( _s / 86400 ))
    _hours=$(( (_s % 86400) / 3600 ))
    _mins=$(( (_s % 3600) / 60 ))
    if [ "$_days" -gt 0 ]; then
        printf '%dd %dh' "$_days" "$_hours"
    elif [ "$_hours" -gt 0 ]; then
        printf '%dh %dm' "$_hours" "$_mins"
    else
        printf '%dm' "$_mins"
    fi
}

fmt_elapsed() {
    # fmt_elapsed <resets_at_epoch> <window_seconds>
    # Output: "Xh Ym/5h" showing how much of the window has elapsed
    _resets_at="$1"
    _window="$2"
    _now=$(date +%s)
    _remaining=$(( _resets_at - _now ))
    [ "$_remaining" -le 0 ] && return
    _elapsed=$(( _window - _remaining ))
    [ "$_elapsed" -lt 0 ] && _elapsed=0
    fmt_duration "$_elapsed"
}

# --- Read stdin and parse JSON ---
INPUT=$(cat)

MODEL="" CWD="" CTX_PCT="" RATE_5H="" RESET_5H="" RATE_7D="" RESET_7D=""
eval "$( printf '%s' "$INPUT" | $JQ -r '
    "MODEL="   + (.model.display_name // "" | @sh),
    "CWD="     + (.cwd // "" | @sh),
    "CTX_PCT=" + ((.context_window.used_percentage // 0) | round | tostring | @sh),
    "RATE_5H=" + (if .rate_limits.five_hour.used_percentage != null then (.rate_limits.five_hour.used_percentage | round | tostring) else "" end | @sh),
    "RESET_5H="+ (.rate_limits.five_hour.resets_at // "" | tostring | @sh),
    "RATE_7D=" + (if .rate_limits.seven_day.used_percentage != null then (.rate_limits.seven_day.used_percentage | round | tostring) else "" end | @sh),
    "RESET_7D="+ (.rate_limits.seven_day.resets_at // "" | tostring | @sh)
' 2>/dev/null )" || exit 0

# --- CWD: last 3 segments, with ~ substitution ---
SHORT_CWD="$CWD"
case "$CWD" in "$HOME"*)
    SHORT_CWD="~${CWD#"$HOME"}"
esac
SHORT_CWD=$(printf '%s' "$SHORT_CWD" | awk -F/ '{
    n = NF
    if (n <= 3) { print; next }
    printf "%s/%s/%s", $(n-2), $(n-1), $n
}')

# --- VCS branch (inlined from jj_status.sh) ---
VCS_BRANCH=""
if [ -n "$CWD" ] && [ -n "$JJ" ] && "$JJ" -R "$CWD" root >/dev/null 2>&1; then
    _output=$("$JJ" -R "$CWD" log \
        -r 'heads(::@ & bookmarks()) | (heads(::@ & bookmarks())..@)' \
        --no-graph \
        -T 'if(local_bookmarks, "B:" ++ local_bookmarks.join(","), "D") ++ "\n"' \
        2>/dev/null) || true
    _bookmark=$(printf '%s' "$_output" | grep '^B:' | sed 's/^B://')
    if [ -n "$_bookmark" ]; then
        _distance=$(printf '%s' "$_output" | grep -c '^D$' || true)
        if [ "${_distance:-0}" -eq 0 ] 2>/dev/null; then
            VCS_BRANCH="$_bookmark"
        else
            VCS_BRANCH="${_bookmark}~${_distance}"
        fi
    fi
elif [ -n "$CWD" ] && [ -n "$GIT" ]; then
    VCS_BRANCH=$("$GIT" -C "$CWD" symbolic-ref --short HEAD 2>/dev/null) || true
fi

# --- Line 1: CWD VCS │ Model ---
LINE1=$(seg "$FG_CWD" "$SHORT_CWD")
if [ -n "$VCS_BRANCH" ]; then
    LINE1="${LINE1}$(sep)$(seg "$FG_VCS" "$VCS_BRANCH")"
fi
if [ -n "$MODEL" ]; then
    LINE1="${LINE1}$(sep)$(seg "$FG_MODEL" "$MODEL")"
fi

# --- Line 2: CTX bar │ 5h elapsed/total bar used% │ 7d elapsed/total bar used% ---
# Format: "Xh Ym/5h (bar) used%"  — elapsed shows how far into the window we are.
LINE2="$(seg "$FG_CTX" "Ctx:")$(make_bar "$CTX_PCT")$(seg "$FG_CTX" " ${CTX_PCT}%")"

if [ -n "$RATE_5H" ] && [ "$RATE_5H" != "null" ]; then
    _5h_elapsed=""
    if [ -n "$RESET_5H" ] && [ "$RESET_5H" != "null" ]; then
        _5h_elapsed=$(fmt_elapsed "$RESET_5H" 18000)
    fi
    _5h_label="${_5h_elapsed:+${_5h_elapsed}/}5h:"
    _5h_seg="$(seg "$FG_5H" "${_5h_label}")$(make_bar "$RATE_5H")$(seg "$FG_5H" " ${RATE_5H}%")"
    LINE2="${LINE2}$(sep)${_5h_seg}"
fi

if [ -n "$RATE_7D" ] && [ "$RATE_7D" != "null" ]; then
    _7d_elapsed=""
    if [ -n "$RESET_7D" ] && [ "$RESET_7D" != "null" ]; then
        _7d_elapsed=$(fmt_elapsed "$RESET_7D" 604800)
    fi
    _7d_label="${_7d_elapsed:+${_7d_elapsed}/}7d:"
    _7d_seg="$(seg "$FG_7D" "${_7d_label}")$(make_bar "$RATE_7D")$(seg "$FG_7D" " ${RATE_7D}%")"
    LINE2="${LINE2}$(sep)${_7d_seg}"
fi

# --- Output ---
printf '%b\n%b\n' "$LINE1" "$LINE2"
