#!/usr/bin/env bash
set -euo pipefail

# Every argument, --help included, belongs to agy, so this wrapper defines no usage of its own.
readonly AGY_BIN="${AGY_BIN:?AGY_BIN is required}"

# agy defines --disable_telemetry only on its acp subcommand and exits 2 on it anywhere else.
if [[ "${1:-}" == acp ]]; then
  shift
  set -- acp --disable_telemetry "$@"
fi
exec -a agy "$AGY_BIN" "$@"
