#!/bin/bash
# Show Claude Code rate limit usage for a single window.
# Usage: rate_limit.sh [5h|7d]  (default: 5h)
# Caches API response for 120 seconds (2 minutes); max ~30 req/hour.
# Falls back to exponential backoff (2m→4m→…→30m) on HTTP 429.

PYTHON="$HOME/.local/bin/python3.14"
CACHE_FILE="/tmp/claude-rate-limit-cache.json"
BACKOFF_FILE="/tmp/claude-rate-limit-backoff"
CACHE_TTL=120
BACKOFF_BASE=120
BACKOFF_MAX=1800
MODE="${1:-5h}"

# Consume stdin passed by ccstatusline
cat > /dev/null

_in_backoff() {
    local until
    [[ -f "$BACKOFF_FILE" ]] || return 1
    until=$(cat "$BACKOFF_FILE" 2>/dev/null)
    [[ -n "$until" ]] && (( $(date +%s) < until ))
}

_set_backoff() {
    local count=0
    [[ -f "${BACKOFF_FILE}.count" ]] && count=$(cat "${BACKOFF_FILE}.count")
    count=$((count + 1))
    local delay=$(( BACKOFF_BASE * (2 ** (count - 1)) ))
    [[ $delay -gt $BACKOFF_MAX ]] && delay=$BACKOFF_MAX
    echo $(($(date +%s) + delay)) > "$BACKOFF_FILE"
    echo "$count" > "${BACKOFF_FILE}.count"
}

fetch_usage() {
    local creds token http_code
    creds=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
    [[ -z "$creds" ]] && return 1
    token=$(printf '%s' "$creds" | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); print(d.get('claudeAiOauth',d).get('accessToken',''))" 2>/dev/null)
    [[ -z "$token" ]] && return 1

    http_code=$(curl -s -o /tmp/claude-rate-limit-resp.tmp \
        -w "%{http_code}" \
        -H "Authorization: Bearer $token" \
        -H "anthropic-beta: oauth-2025-04-20" \
        https://api.anthropic.com/api/oauth/usage 2>/dev/null)

    if [[ "$http_code" == "200" ]]; then
        mv /tmp/claude-rate-limit-resp.tmp "$CACHE_FILE"
        rm -f "$BACKOFF_FILE" "${BACKOFF_FILE}.count"
        return 0
    elif [[ "$http_code" == "429" ]]; then
        _set_backoff
        rm -f /tmp/claude-rate-limit-resp.tmp
        return 1
    else
        rm -f /tmp/claude-rate-limit-resp.tmp
        return 1
    fi
}

format_output() {
    "$PYTHON" - "$CACHE_FILE" "$MODE" << 'EOF'
import sys, json

with open(sys.argv[1]) as f:
    data = json.load(f)

def bar(util):
    util = min(max(float(util), 0.0), 1.0)
    filled = round(util * 10)
    return "▰" * filled + "▱" * (10 - filled) + f" {int(util * 100)}%"

mode = sys.argv[2]
if mode == "7d":
    label, key = "7d", "seven_day"
else:
    label, key = "5h", "five_hour"

util = data.get(key, {}).get("utilization", 0) / 100
print(f"{label} {bar(util)}", end="")
EOF
}

# Refresh cache if not in backoff and cache is stale or missing
if ! _in_backoff; then
    if [[ ! -f "$CACHE_FILE" ]] || (( $(date +%s) - $(stat -f %m "$CACHE_FILE") >= CACHE_TTL )); then
        fetch_usage
        [[ ! -f "$CACHE_FILE" ]] && exit 0
    fi
fi

[[ ! -f "$CACHE_FILE" ]] && exit 0
format_output
