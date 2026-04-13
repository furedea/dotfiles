# Phase 2: Python (uv)

Prerequisite: Phase 1 done with `templates/python/flake.nix`. `which uv` and `which python3` should both resolve under `/nix/store/`.

## Steps

1. `uv init` — generates a minimal `pyproject.toml` + `main.py`.
2. Merge `templates/python/pyproject.toml` (in this skill's directory) into the generated one. Keep the generated `[project]` name/version; bring in the `[tool.*]` and dependency sections from the template.
3. Copy `templates/python/gitignore` (in this skill's directory) to the project root as `.gitignore` (covers `.venv/` etc — note the leading dot is dropped on disk to avoid macOS hidden-file gotchas in the template folder, rename on copy).
4. Relax `requires-python` to whatever `python3 --version` prints inside the direnv shell.
5. Hand off to the `python-style` skill.

## Why uv is pinned to the nix interpreter

The Python template sets `UV_PYTHON_DOWNLOADS=never` + `UV_PYTHON_PREFERENCE=only-system` so uv cannot silently download a `python-build-standalone` binary into `~/.local/share/uv/python/`. Without that, you end up with two interpreters on one machine — nix's and uv's — and neither is reproducible from the other. With it, **nix is the single source of truth** for the interpreter and uv is reduced to resolver + lockfile + venv.

If nix's `python3` is too old for `requires-python`, uv fails loudly. That is the correct failure mode — fix it by bumping nixpkgs, not by unsetting the env vars.

## Common first-run checks

- `uv sync` succeeds **without downloading a Python** — this is the only direct confirmation that `UV_PYTHON_DOWNLOADS=never` is in effect.
- `python -c "import sys; print(sys.executable)"` prints a path under `.venv/` whose interpreter symlinks back to `/nix/store/...-python3-*`.

## What NOT to do

- Do not unset `UV_PYTHON_DOWNLOADS` / `UV_PYTHON_PREFERENCE` to "just make it work". Those env vars are load-bearing; removing them silently reintroduces the two-interpreter problem this skill exists to prevent.
- Do not commit `.venv/` — it is a cache keyed to the nix store path and will rot on any flake update.
