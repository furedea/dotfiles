# TeX / LaTeX Setup

Use after [development environment setup](dev_environment.md). The default for new projects is
`furedea/template-tex`. Setup verifies the typesetting chain rather than a package-manager init.

## Setup and Verification

1. Inspect the project's TeX engine, source entry point, fonts, bibliography tools, and build
   configuration. Preserve an existing engine and driver instead of imposing a new one.
2. For a new project, create only missing source and build entry points. Prefer `latexmk` when
   automatic bibliography and rerun handling is useful; a small existing Makefile or recipe is
   also valid.
3. Verify the required engine and driver in the project environment. For a XeLaTeX project, a
   smoke build can be `direnv exec . latexmk -xelatex main.tex`; use the actual entry point and
   engine for other projects. Check that the expected PDF was produced successfully.
4. Reuse hook evidence for tex-fmt/chktex checks. If their availability or behavior remains
   unverified, use the project's narrowest configured check without unnecessarily rewriting source.

## Distribution and Reproducibility

TeX package and font versions can affect layout, so preserve the project's `flake.lock` and
inspect output when intentionally updating dependencies. Stable and unstable nixpkgs inputs both
need locking for reproducibility; this is not a TeX-only requirement. Each project's lock is its
own authority. Template maintenance is a separate task, not a synchronization side effect of setup.

The template's full TeX Live scheme favors package availability over download and closure size.
Keep it as the default unless project constraints justify a smaller distribution. Do not install
another TeX Live through Homebrew or tlmgr alongside a Nix-owned distribution to work around
missing packages; fix the declared environment instead.
