#!/bin/bash

# lint_format_rs.sh
# Format and lint Rust files via rustfmt and clippy.

set -eo pipefail
# shellcheck source=lib/lint_format.sh
source "$(dirname "$0")/lib/lint_format.sh"

load_file_path # sets FILE_PATH, FILENAME

require_cmd rustfmt
rustfmt "$FILE_PATH" 2>&1 || {
  echo "❌ rustfmt failed for $FILENAME"
  exit 1
}
echo "✅ rustfmt completed for $FILENAME"

require_cmd cargo

CARGO_DIR=$(find_project_root "$(dirname "$FILE_PATH")" Cargo.toml) || {
  echo "⚠️  Cargo.toml not found, skipping clippy"
  exit 0
}

cd "$CARGO_DIR"
cargo clippy --quiet -- -D warnings 2>&1 || {
  echo "❌ clippy failed for $FILENAME"
  exit 1
}
echo "✅ clippy completed for $FILENAME"
