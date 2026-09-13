#!/usr/bin/env bash
# Keep the shell entry point; Python owns the workflow.
set -euCo pipefail

function run_python() {
  local _python="${XDG_CONFIG_HOME:-$HOME/.config}/dotfiles/bin/python3"
  [[ -x "$_python" ]] || _python=python3
  exec "$_python" -I -B -c '
import pathlib
import runpy
import sys

script = pathlib.Path(sys.argv.pop(1)).resolve().with_name("lint_format.py")
sys.argv[0] = str(script)
runpy.run_path(str(script), run_name="__main__")
' "${BASH_SOURCE[0]}" nix "$@"
}

function usage() {
  run_python --help
}

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && usage
run_python "$@"
