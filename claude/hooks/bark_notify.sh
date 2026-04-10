#!/bin/bash
# Send iOS push notification via Bark with AES-256-CBC encryption.
# Requires: BARK_DEVICE_KEY, BARK_ENCRYPT_KEY, BARK_ENCRYPT_IV (loaded by dotenvx)
# Input: JSON from stdin (Claude Code hook format)
# Usage: bark_notify.sh <message>
set -euo pipefail

readonly BARK_API_BASE="https://api.day.app"
readonly DEFAULT_MESSAGE="$1"

INPUT=$(cat)

TITLE=$(echo "$INPUT" | python3 -c \
	"import sys,json; d=json.load(sys.stdin); print(d.get('title','Claude Code'))" 2>/dev/null ||
	echo "Claude Code")

MESSAGE=$(echo "$INPUT" | python3 -c \
	"import sys,json; d=json.load(sys.stdin); print(d.get('message','$DEFAULT_MESSAGE'))" 2>/dev/null ||
	echo "$DEFAULT_MESSAGE")

# Convert ASCII hex strings to hex-of-hex for openssl -K/-iv
KEY_HEX=$(printf '%s' "$BARK_ENCRYPT_KEY" | xxd -ps -c 200)
IV_HEX=$(printf '%s' "$BARK_ENCRYPT_IV" | xxd -ps -c 200)

# Build plaintext JSON payload and encrypt with AES-256-CBC
PLAINTEXT=$(python3 -c "
import json, sys
print(json.dumps({'title': sys.argv[1], 'body': sys.argv[2]}))
" "$TITLE" "$MESSAGE")

CIPHERTEXT=$(echo -n "$PLAINTEXT" | openssl enc -aes-256-cbc \
	-K "$KEY_HEX" \
	-iv "$IV_HEX" \
	-base64 -A 2>/dev/null)

# Send ciphertext and IV as separate form-encoded parameters
curl -sf \
	--data-urlencode "ciphertext=${CIPHERTEXT}" \
	--data-urlencode "iv=${BARK_ENCRYPT_IV}" \
	"${BARK_API_BASE}/${BARK_DEVICE_KEY}" >/dev/null
