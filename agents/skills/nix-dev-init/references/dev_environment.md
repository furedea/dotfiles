# Project Development Environment

Use this reference for new or existing projects, including local-only projects. GitHub creation
and standard remote settings are optional, separate operations.

## Inspect and Adapt

Inspect the target project's environment definitions, manifests, lockfiles, supported platforms,
CI, and hook configuration. For an existing project, preserve its conventions and introduce only
the requested Nix integration; do not rerun language initialization over existing manifests.
For a new project, reuse the selected template before creating missing files.

- Define the complete project toolchain and non-secret environment in the project's devShell.
  Global fallback runtimes can remain installed but are not substitutes for project declarations.
- Use the project's pinned package set to select its runtime/compiler, package manager, and
  required quality tools. Prefer available packages over speculative overlays. Do not hard-code
  template versions or assume a global registry resolves to the same nixpkgs revision.
- Preserve `flake.lock` and language lockfiles. Create missing locks when needed; update existing
  entries only for an intentional dependency or environment change, and inspect the resulting diff.
  Do not synchronize locks with unrelated projects or templates during setup.
- Support the platforms actually required by development and CI. Do not add multi-system helpers
  or extra flake inputs speculatively.
- Keep `.envrc` minimal (`use flake` for a new Nix-only setup). Preserve existing integrations when
  adopting Nix into a project. Avoid duplicating toolchain paths or versions there.
- Keep secrets outside Nix expressions and the store. When needed, use ignored local secret files
  and the project's loader, such as `dotenv .env`; do not print their contents for diagnostics.
- Ensure ignore rules cover `.direnv/`, `result`, `result-*`, and language-specific caches without
  replacing existing ignore rules. Keep `.venv/`, `node_modules/`, and `target/` out of version
  control where applicable. Never edit `.direnv/` as configuration.

Git is not a prerequisite for evaluating a local flake. In a Git-backed flake, new source files
must be visible to Nix through Git tracking; stage only the relevant files when needed, respecting
existing staging. Neither flake evaluation nor direnv trust requires a commit.

## Activate Before Language Setup

1. Review `.envrc` and the setup code it invokes before authorizing it with `direnv allow`.
   Re-authorize if its approved contents change; do not automatically trust unreviewed code.
2. Run language commands in the project directory with `direnv exec . <command>`, or in a shell
   whose project environment is demonstrably active. Do not assume `direnv allow` or `cd` activates
   the environment in an agent's non-interactive shell or carries it across separate tool calls.
3. Use `nix develop --command <command>` when only the flake environment is required, including
   diagnosis without direnv. It does not load additional `.envrc` integrations or secret loaders.
4. After changing the flake, reload and confirm the new environment is in use. Investigate stale
   or fallback environments rather than continuing with an old toolchain after evaluation fails.

Project flakes do not require `darwin-rebuild switch` or Home Manager activation. Do not install
missing project tools globally or through a second toolchain manager to bypass setup failures.

## Verify the Effective Environment

Inside the selected environment, check required tool versions and executable locations against
the project definition and lock. A `/nix/store/` path alone is insufficient: global tools are also
Nix-managed. Confirm tools are declared in the project and investigate any path/version mismatch;
use the language notes below for dependency-environment checks.

When loading fails, inspect `direnv status`, trust status, and the flake evaluation error. Use a
targeted command such as `nix develop --command <tool> --version`; do not dump the environment.
Run language initialization only for genuinely missing scaffolding. Otherwise, use the project's
actual dependency sync/build entry point inside the active environment and obtain a minimal
successful smoke result. Review necessary lock changes caused by manifest adjustments or template
renames, without upgrading unrelated dependencies. Confirm required dependency groups and tools
are usable, then hand off to the development conventions listed in the main skill.

Reuse successful hook evidence as described in the main skill. If required lint, format, typecheck,
or test evidence is missing, use the project's narrowest configured check without unnecessarily
rewriting source. Throwaway Nix-shell experiments do not replace a durable project's declared
toolchain and lock.

## Editor Tooling

Prefer the existing global editor/LSP installation instead of adding every LSP to every devShell.
Environment inheritance, interpreter discovery, sysroots, and version compatibility still need
checking when an editor issue occurs; automatic discovery is not a guarantee. Add project-local
editor tooling when a concrete compatibility requirement justifies it.

## Language-Specific Notes

### Python / uv

Match the devShell's Python to `pyproject.toml`'s `requires-python` and any explicit interpreter
selection. Keep `UV_PYTHON_DOWNLOADS=never` and `UV_PYTHON_PREFERENCE=only-system` for Nix-managed
Python: these disable downloads and uv-managed interpreter selection, but do not identify the
project interpreter by themselves. Verify their effective values and the selected Python.

Nix owns the interpreter; uv owns dependency resolution, the language lock, and `.venv`. Run
`uv sync` in the project environment and confirm the resulting virtual environment uses the
expected Nix Python, for example with:

```sh
direnv exec . uv run python -c 'import os, sys; print(sys.executable); print(os.path.realpath(sys.executable)); print(sys.base_prefix)'
```

Successful sync without a download is not proof of interpreter identity or download policy.
Diagnose an existing `.venv` pointing to an old or non-project interpreter before recreating it
through the normal uv workflow. Resolve toolchain/requirement mismatches instead of disabling
the policy; upgrading nixpkgs is one possible remedy, not an automatic one.

Follow `python-style` for missing layout: use `src/<package_name>/` only when package semantics
are needed. `uv init` is for a missing initial manifest, not a template that already supplies one.

### Rust / Cargo

Inspect `Cargo.toml`, workspace configuration, and toolchain requirements. Verify Cargo, rustc,
and required components such as rustfmt and Clippy from the intended toolchain. Use `cargo init`
only for missing scaffolding; a build smoke check can be `direnv exec . cargo build`.

Prefer nixpkgs' Cargo and rustc when sufficient, avoiding an extra flake input. Add another
toolchain source only for a concrete release, nightly, or target requirement. Do not create
`rust-toolchain.toml` merely because the project uses Rust; respect existing rustup or toolchain
file requirements and make the Nix integration explicit. Do not install competing rustup tools
to bypass a Nix-owned toolchain failure. For rust-analyzer issues, check the effective sysroot
and component compatibility using the editor guidance above.

### TypeScript / Node

Match Node and the package manager to the devShell and `package.json` declarations. pnpm is the
new-project default, sharing a content-addressed cache; reproducibility still depends on the
toolchain, lock, and installation settings. Preserve existing package-manager choices and
registries unless migration is requested; do not mix managers or introduce a competing lock.

For pnpm projects, run `pnpm install` in the project environment and verify the actual project
scripts. Use `pnpm init` only when the manifest is missing. Retain the template's oxlint/oxfmt
setup unless a concrete need, such as existing upstream conventions, justifies different tools.

### TeX / LaTeX

Inspect the engine, source entry point, fonts, bibliography tools, and build configuration.
Preserve an existing engine/driver and create only missing entry points. Prefer `latexmk` when
automatic bibliography and rerun handling is useful; an existing Makefile or recipe is also valid.
For XeLaTeX, a smoke build can be `direnv exec . latexmk -xelatex main.tex`; use the actual entry
point and engine, and confirm successful PDF generation. Quality checks use tex-fmt/chktex where
configured, following the common verification policy above.

Package and font versions can affect layout: inspect output when intentionally updating them.
Stable and unstable inputs both require locks; this is not a TeX-only requirement. The full
TeX Live scheme favors package availability over download and closure size; keep this default
unless constraints justify a smaller distribution. Fix missing packages in the Nix declaration,
not through an additional Homebrew or tlmgr-managed distribution.

### Other Languages and Repeated Patterns

Add language tools to the minimal template without removing its shared tooling, then follow the
common initialization and verification steps above. Do not create a new template for the first
use of a language. If several projects demonstrate a reusable pattern, propose a separate
template-maintenance task: derive from the minimal template, add the language environment and
conventions, extend name substitution only if needed, and update the template table and language
notes. Reuse the common repository policy rather than inventing language-specific ruleset files.
