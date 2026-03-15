#!/bin/bash
set -euo pipefail
osascript -e 'display notification "Claude Codeが許可を求めています" with title "Claude Code" subtitle "確認待ち"'
afplay /System/Library/Sounds/Submarine.aiff
