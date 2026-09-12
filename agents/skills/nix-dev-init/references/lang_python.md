# Python / uv Setup

Use after [development environment setup](dev_environment.md). The default for new projects is
`furedea/template-python`; existing projects retain their manifests and layout.

## Setup and Verification

1. Inspect `pyproject.toml`, the lock, and the devShell. Match its Python to `requires-python` and
   any explicit interpreter selection. Run the following commands in the project environment.
2. Keep `UV_PYTHON_DOWNLOADS=never` and `UV_PYTHON_PREFERENCE=only-system` for the Nix-managed
   toolchain. These disable downloads and uv-managed interpreter selection; they do not identify
   the project's Nix interpreter by themselves. Verify the effective settings and selected Python.
3. Reuse existing source and tests. Follow `python-style` for any missing layout: do not create
   `src/<package_name>/` unless the project needs a package namespace. Use `uv init` only when an
   initial manifest is genuinely missing and setup requires it, not over a template manifest.
4. Run `uv sync` to prepare dependencies. Preserve the existing lock; review any necessary changes
   caused by manifest adjustments instead of upgrading dependencies as part of bootstrap.
5. Check the resulting interpreter, for example with:

    ```sh
    direnv exec . uv run python -c 'import os, sys; print(sys.executable); print(os.path.realpath(sys.executable)); print(sys.base_prefix)'
    ```

    Confirm the project virtual environment uses the expected Nix Python. Successful sync without
    a download is not proof of interpreter identity or of the effective download policy.

6. Confirm the required dependency groups are usable and hand off to `python-style`.

## Interpreter Ownership

Nix owns the interpreter; uv owns dependency resolution, the language lock, and the virtual
environment. If Python requirements cannot be met, resolve the project toolchain/requirement
mismatch rather than disabling the download policy. A nixpkgs upgrade is one possible change,
not an automatic remedy for every mismatch.

An existing `.venv` may reference an older or non-project interpreter. Diagnose it before replacing
it, then recreate through the project's normal uv workflow when needed. Do not commit `.venv`.
