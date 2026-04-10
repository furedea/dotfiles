#!/bin/sh
# jj prompt for Starship: outputs "bookmark~distance (change_id)" format.
# Falls back to git branch if not a jj repo.

JJ=$(command -v jj) || exit 0
GIT=$(command -v git) || GIT=""
CWD="${1:-$(pwd)}"

if "$JJ" -R "$CWD" root >/dev/null 2>&1; then
	output=$("$JJ" -R "$CWD" log \
		-r 'heads(::@ & bookmarks()) | (heads(::@ & bookmarks())..@)' \
		--no-graph \
		-T 'if(local_bookmarks, "B:" ++ local_bookmarks.join(","), "D") ++ "\n"' \
		2>/dev/null) || exit 0

	bookmark=$(printf '%s' "$output" | grep '^B:' | sed 's/^B://')
	[ -z "$bookmark" ] && exit 0

	distance=$(printf '%s' "$output" | grep -c '^D$' || true)
	change_id=$("$JJ" -R "$CWD" log -r @ --no-graph \
		-T 'change_id.shortest(8) ++ "\n"' 2>/dev/null) || true

	if [ "${distance:-0}" -eq 0 ]; then
		label="$bookmark"
	else
		label="${bookmark}~${distance}"
	fi

	if [ -n "$change_id" ]; then
		printf '%s (%s)' "$label" "$change_id"
	else
		printf '%s' "$label"
	fi
	exit 0
fi

# git fallback
if [ -n "$GIT" ]; then
	branch=$("$GIT" -C "$CWD" symbolic-ref --short HEAD 2>/dev/null) || exit 0
	commit=$("$GIT" -C "$CWD" rev-parse --short HEAD 2>/dev/null) || true
	if [ -n "$commit" ]; then
		printf '%s (%s)' "$branch" "$commit"
	else
		printf '%s' "$branch"
	fi
fi
