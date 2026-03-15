#!/bin/bash

# format-and-lint.sh
# Auto-format and lint files based on their extension

set -e

# Get the file path from argument or stdin JSON (Claude Code hook passes data via stdin)
if [ -n "$1" ]; then
    FILE_PATH="$1"
else
    INPUT=$(cat)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
fi

# Check if file path is provided
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
    echo "File not found: $FILE_PATH"
    exit 1
fi

# Get file extension
EXTENSION="${FILE_PATH##*.}"
FILENAME=$(basename "$FILE_PATH")

echo "Processing file: $FILENAME (.$EXTENSION)"

# Process based on file extension
case "$EXTENSION" in
    "py")
        echo "Running ruff on Python file..."
        if command -v uv &> /dev/null; then
            # Find the project root directory by looking for pyproject.toml or uv.lock
            PROJECT_DIR=$(dirname "$FILE_PATH")
            while [ "$PROJECT_DIR" != "/" ] && [ ! -f "$PROJECT_DIR/pyproject.toml" ] && [ ! -f "$PROJECT_DIR/uv.lock" ]; do
                PROJECT_DIR=$(dirname "$PROJECT_DIR")
            done

            if [ -f "$PROJECT_DIR/pyproject.toml" ] || [ -f "$PROJECT_DIR/uv.lock" ]; then
                cd "$PROJECT_DIR"
                # Format with ruff via uv
                uv run --frozen ruff format "$FILE_PATH" 2>&1 || {
                    echo "❌ uv run ruff format failed for $FILENAME"
                    exit 1
                }
                # Lint with ruff via uv
                uv run --frozen ruff check "$FILE_PATH" 2>&1 || {
                    echo "❌ uv run ruff check failed for $FILENAME"
                    exit 1
                }
                echo "✅ ruff formatting and linting completed for $FILENAME"
            else
                echo "⚠️  No Python project found (pyproject.toml or uv.lock), skipping Python formatting/linting"
            fi
        else
            echo "⚠️  uv not found, skipping Python formatting/linting"
        fi
        ;;
    "js"|"ts"|"jsx"|"tsx")
        echo "Running biome on JavaScript/TypeScript file..."
        if command -v biome &> /dev/null; then
            # Format and lint with biome
            biome format --write "$FILE_PATH" 2>&1 || {
                echo "❌ biome format failed for $FILENAME"
                exit 1
            }
            biome lint "$FILE_PATH" 2>&1 || {
                echo "❌ biome lint failed for $FILENAME"
                exit 1
            }
            echo "✅ biome formatting and linting completed for $FILENAME"
        else
            echo "⚠️  biome not found, skipping JavaScript/TypeScript formatting/linting"
        fi
        ;;
    "rs")
        echo "Running rustfmt and clippy on Rust file..."
        if command -v rustfmt &> /dev/null; then
            # Format with rustfmt
            rustfmt "$FILE_PATH" 2>&1 || {
                echo "❌ rustfmt failed for $FILENAME"
                exit 1
            }
            echo "✅ rustfmt formatting completed for $FILENAME"
        else
            echo "⚠️  rustfmt not found, skipping Rust formatting"
        fi

        if command -v cargo &> /dev/null; then
            # Lint with clippy (requires cargo project)
            CARGO_DIR=$(dirname "$FILE_PATH")
            while [ "$CARGO_DIR" != "/" ] && [ ! -f "$CARGO_DIR/Cargo.toml" ]; do
                CARGO_DIR=$(dirname "$CARGO_DIR")
            done

            if [ -f "$CARGO_DIR/Cargo.toml" ]; then
                cd "$CARGO_DIR"
                cargo clippy --quiet -- -D warnings 2>&1 || {
                    echo "❌ clippy failed for $FILENAME"
                    exit 1
                }
                echo "✅ clippy linting completed for $FILENAME"
            else
                echo "⚠️  Cargo.toml not found, skipping clippy linting"
            fi
        else
            echo "⚠️  cargo not found, skipping clippy linting"
        fi
        ;;
    *)
        echo "ℹ️  No formatter/linter configured for .$EXTENSION files"
        ;;
esac

echo "Processing completed for $FILENAME"
