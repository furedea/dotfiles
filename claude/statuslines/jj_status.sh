#!/bin/bash
# Show VCS branch info.
# jj repo: "main~2" (bookmark + distance from nearest ancestor bookmark)
# git repo: "branch-name"
# Reads Claude Code status JSON from stdin.

JQ=/opt/homebrew/bin/jq
JJ=/opt/homebrew/bin/jj
GIT=/usr/bin/git

input=$(cat)
cwd=$(printf '%s' "$input" | $JQ -r '.cwd // empty' 2>/dev/null)

[ -z "$cwd" ] && exit 0

# --- jj repo ---
if $JJ -R "$cwd" root > /dev/null 2>&1; then
    # Single jj call: union of bookmark commit and commits between it and @.
    # Template marks each line as "B:<name>" (bookmark) or "D" (distance unit).
    output=$($JJ -R "$cwd" log \
        -r 'heads(::@ & bookmarks()) | (heads(::@ & bookmarks())..@)' \
        --no-graph \
        -T 'if(local_bookmarks, "B:" ++ local_bookmarks.join(","), "D") ++ "\n"' \
        2>/dev/null)

    bookmark=$(printf '%s' "$output" | grep '^B:' | sed 's/^B://')
    [ -z "$bookmark" ] && exit 0
    distance=$(printf '%s' "$output" | grep -c '^D$')

    if [ "${distance:-0}" -eq 0 ] 2>/dev/null; then
        printf '%s' "$bookmark"
    else
        printf '%s~%s' "$bookmark" "$distance"
    fi
    exit 0
fi

# --- git repo ---
branch=$($GIT -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)
[ -z "$branch" ] && exit 0
printf '%s' "$branch"
