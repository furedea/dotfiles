# Phase 2: TeX / LaTeX

Prerequisite: Phase 1 complete with `templates/tex/flake.nix` **and** `templates/tex/flake.lock` — the TeX template is the only one where the lock is copied in alongside the flake. Verify `which latexmk` or `which xelatex` resolves under `/nix/store/` before proceeding.

TeX does not have an `init` command in the usual sense; Phase 2 here is about project scaffolding and verifying the typesetting chain, not a package manager bootstrap.

## Steps

1. Create the source entry point — typically `main.tex` — or `cp` an existing project skeleton if one is available.
2. Decide on a build driver:
   - `latexmk` (recommended, handles bib / rerun automatically)
   - or a thin `Makefile` / `just` recipe wrapping `xelatex` + `biber`
3. Copy `templates/tex/gitignore` to the project `.gitignore` — covers `.direnv/`, `result*`, and all TeX build artifacts in one shot. Mirrored from `~/dev/tex/shigyo/.gitignore`.
4. Test-build once: `latexmk -xelatex main.tex` (or equivalent). First build may take noticeable time because `texlive.combined.scheme-full` is large.

## Why `flake.lock` is checked in here (and nowhere else)

TeX Live output is exquisitely sensitive to package versions — a single `tlpdb` update can silently change kerning, font metrics, or break `chktex` / `tex-fmt`. For most languages "track a stable channel" is good enough because the toolchain is semver-disciplined; TeX is not.

Consequence: the TeX template pins to `nixpkgs-unstable` (because TeX Live lands on unstable first) **and** ships a `flake.lock` so "unstable + reproducible" is coherent. The two together are load-bearing — dropping either one breaks the guarantee.

**Mirror rule**: `templates/tex/flake.lock` and `templates/tex/gitignore` both mirror `~/dev/tex/shigyo/`. If `shigyo` runs `nix flake update` or edits its `.gitignore`, re-copy those files here so freshly-initialized TeX projects stay aligned with the primary one. Do not `nix flake update` the skill template in isolation.

## Why `scheme-full`

`texlive.combined.scheme-full` is the complete distribution — large (~5 GB) but avoids the "missing package" rabbit hole where every project adds one more `texlivePackages.*`. Disk is cheap compared to debugging "why does `\usepackage{foo}` fail on this machine". When a project has hard closure-size constraints (CI runners, containers) switch to a narrower scheme as a one-off exception.

## Common first-run checks

- `xelatex --version` should print a recent TeX Live version.
- `latexmk -xelatex main.tex` should produce `main.pdf` on a minimal `\documentclass{article}` source.
- `tex-fmt main.tex` and `chktex main.tex` should both run without "command not found".

## What NOT to do

- Do not drop `flake.lock` "to match the other templates". TeX is the exception for the reason above.
- Do not switch the TeX template from `nixpkgs-unstable` to `nixpkgs-25.11-darwin` without also re-evaluating whether the lock still makes sense.
- Do not install TeX Live via `brew` / `tlmgr` on the side. That reintroduces two sources of truth for packages.
