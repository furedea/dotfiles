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

SEP=" │ "

# --- Helpers ---
seg() {
    # seg <fg> <text>
    printf '\033[1;38;5;%dm%s\033[0m' "$1" "$2"
}

sep() {
    printf '\033[38;5;%dm%s\033[0m' "$FG_SEP" "$SEP"
}

fmt_remaining() {
    # fmt_remaining <resets_at_epoch>
    # Output: "(Xd Yh)" or "(Xh Ym)" or "(Xm)"
    _resets_at="$1"
    _now=$(date +%s)
    _diff=$(( _resets_at - _now ))
    [ "$_diff" -le 0 ] && return

    _days=$(( _diff / 86400 ))
    _hours=$(( (_diff % 86400) / 3600 ))
    _mins=$(( (_diff % 3600) / 60 ))

    if [ "$_days" -gt 0 ]; then
        printf '(%dd %dh)' "$_days" "$_hours"
    elif [ "$_hours" -gt 0 ]; then
        printf '(%dh %dm)' "$_hours" "$_mins"
    else
        printf '(%dm)' "$_mins"
    fi
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

# --- Line 2: CTX % │ 5h % (remaining) │ 7d % (remaining) ---
CTX_TEXT="Ctx: ${CTX_PCT}%"
LINE2=$(seg "$FG_CTX" "$CTX_TEXT")

if [ -n "$RATE_5H" ] && [ "$RATE_5H" != "null" ]; then
    _5h_text="5h: ${RATE_5H}%"
    if [ -n "$RESET_5H" ] && [ "$RESET_5H" != "null" ]; then
        _5h_rem=$(fmt_remaining "$RESET_5H")
        [ -n "$_5h_rem" ] && _5h_text="${_5h_text} ${_5h_rem}"
    fi
    LINE2="${LINE2}$(sep)$(seg "$FG_5H" "$_5h_text")"
fi

if [ -n "$RATE_7D" ] && [ "$RATE_7D" != "null" ]; then
    _7d_text="7d: ${RATE_7D}%"
    if [ -n "$RESET_7D" ] && [ "$RESET_7D" != "null" ]; then
        _7d_rem=$(fmt_remaining "$RESET_7D")
        [ -n "$_7d_rem" ] && _7d_text="${_7d_text} ${_7d_rem}"
    fi
    LINE2="${LINE2}$(sep)$(seg "$FG_7D" "$_7d_text")"
fi

# --- Output ---
printf '%b\n%b\n' "$LINE1" "$LINE2"
