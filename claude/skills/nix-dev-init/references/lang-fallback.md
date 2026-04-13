# Phase 2: Fallback (language without a dedicated template)

Use this path when the project's primary language is not Python, TypeScript/Node, Rust, or TeX. Prerequisite: Phase 1 complete with `templates/base/flake.nix` (empty `packages` list).

The goal of this ref is to keep the fallback path **principled**, not to enumerate every language. Do not preemptively create a new template under `templates/<lang>/` just because a project happened to use that language — wait until the language appears multiple times and a pattern is clear. YAGNI.

## Steps

1. Identify the language's canonical nix package names for: compiler/runtime, package manager (if separate), formatter, linter. Use `nix search nixpkgs <name>` or check `search.nixos.org`.
2. Edit `flake.nix` (copied from `templates/base/`) and fill in `devShells.${system}.default.packages` with those derivations. Prefer names that already exist on stable nixpkgs over overlays.
3. `direnv reload` (or just `cd .` after editing the flake — direnv auto-rebuilds on `flake.nix` mtime change).
4. Verify the toolchain is on PATH under `/nix/store/` with `which <tool>`.
5. Run the language's standard init command inside the direnv-activated shell — never on the host shell. Examples: `go mod init`, `mix new`, `dotnet new console`, `zig init-exe`, `elm init`, `deno init`.
6. Add language-specific ignore entries to `.gitignore` on top of the `.direnv/` / `result*` lines from Phase 1.

## Principles that still apply

Everything in Phase 1 still holds regardless of language:

- **Toolchain before init**: run the init command *after* `direnv allow`, never before. The whole reason Phase 1 exists is to prevent the host toolchain from leaking into project lockfiles / manifests.
- **One source of truth**: the devShell in `flake.nix` is the only place the toolchain version should live. Do not duplicate it in `.envrc` via `PATH_add` or inline exports.
- **No LSPs in the devShell**: globally-installed LSPs (in `~/dotfiles`) discover the project toolchain via PATH once direnv activates. Per-project LSPs bloat the closure for no benefit.
- **No host-shell escape hatches**: if "just brew install it" is tempting, stop — that reintroduces the exact host-leak problem this skill exists to prevent.

## When to promote a fallback into a real template

If the same fallback recipe is repeated across ≥3 projects with only trivial variation, it is time to:

1. Create `templates/<lang>/flake.nix` with the shared packages + any env vars.
2. Create `references/lang-<lang>.md` following the structure of the existing language refs (Steps / Why / Common checks / What NOT to do).
3. Update `INSTRUCTIONS.md`'s template table and the SKILL.md router to recognize the new language.

Do not do this for a single project. The overhead of maintaining a template that only has one caller is worse than copy-pasting a few lines of `packages = [ ... ]`.

## What NOT to do

- Do not add the language's toolchain to `~/dotfiles/nix/home/default.nix` "temporarily". Temporary global installs have a way of becoming permanent.
- Do not create a new template under `templates/` on the first use of a language. Wait for the pattern.
- Do not skip Phase 1 and go straight to `go mod init` / `mix new` on the host shell "because it's a quick experiment". Experiments that aren't worth a flake aren't worth committing either — use `nix shell nixpkgs#go` as a throwaway instead.
