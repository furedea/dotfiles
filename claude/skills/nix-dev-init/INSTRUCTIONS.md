# Nix Dev Init Workflow

## Scope

Setting up a **per-project** dev environment — not global dotfiles. For home-manager / nix-darwin edits on `~/dotfiles`, use the `nix-dotfiles` skill instead.

The workflow has two phases, and the split is load-bearing:

- **Phase 1 — Nix shell** (this file): `flake.nix` → `.envrc` → `direnv allow`. Language-agnostic.
- **Phase 2 — Language init** (see `references/lang-<name>.md`): `uv init` / `pnpm init` / `cargo init` / ... **inside the direnv-activated shell**.

The whole reason Phase 1 runs before Phase 2 is so the language's init command sees the nix-provided toolchain on PATH, not the host's. Do not collapse or reorder the phases.

## Mandatory Order (Phase 1)

1. `flake.nix` — write the devShell with the language toolchain
2. `.envrc` — single line: `use flake`
3. `direnv allow` — trust the .envrc once, per repo
4. Proceed to Phase 2 via the relevant `references/lang-<name>.md`

### Why this order

- **Toolchain before init**: running `uv init` on the host shell first picks up the host's `python3`, whose version leaks into `pyproject.toml`'s `requires-python` and lockfiles. On another machine (or in CI) this silently breaks reproducibility.
- **Commit `.envrc` before `direnv allow`**: direnv's trust state is keyed by file hash. Allowing first and editing after immediately invalidates the allow, forcing a re-allow.

## Flake Templates

Pick the template that matches the project's primary language. All templates live under `<this skill's directory>/templates/`. Copy the chosen `flake.nix` (and `flake.lock` where noted) to the project root, then edit `devShells.<system>.default.packages` to add anything the project needs beyond the defaults.

| Project type | Template | devShell packages | Ship `flake.lock`? |
| --- | --- | --- | --- |
| Python (uv, nix-managed interpreter) | `templates/python/flake.nix` | `uv`, `python3` | no |
| TypeScript / Node (pnpm) | `templates/typescript/flake.nix` | `nodejs_22`, `pnpm` | no |
| Rust | `templates/rust/flake.nix` | `cargo`, `rustc`, `rustfmt`, `clippy` | no |
| TeX / LaTeX | `templates/tex/flake.nix` | `texlive.combined.scheme-full`, `tex-fmt`, `texlivePackages.chktex` | **yes** (copy `templates/tex/flake.lock` too) |
| Fallback (unlisted languages) | `templates/flake.nix` | empty list — fill in manually | no |

Non-tex templates intentionally omit `flake.lock`: run `nix flake update` once in the new project to resolve a fresh `nixpkgs` commit. Shipping a skill-side lock for general templates would silently rot.

Do not preemptively generalize to multi-system (`forAllSystems`, `flake-utils`) unless the project actually needs Linux CI. YAGNI.

### Why LSPs are not in the templates

Editor-side tooling (`rust-analyzer`, `pyright`, `typescript-language-server`, …) belongs in the **global** nvim environment, not per-project devShells. When direnv activates the shell it puts the project's `rustc` / `python` / `node` on PATH, and the globally-installed LSP picks those up automatically via `rustc --print sysroot` / `python` discovery. Adding LSPs per project bloats closures for no benefit unless a specific project hits a version mismatch — handle that as a one-off exception, not a default.

### Why the Python template pins uv to the nix interpreter

The Python devShell sets two env vars:

    UV_PYTHON_DOWNLOADS = "never";
    UV_PYTHON_PREFERENCE = "only-system";

These force uv to use the `python3` that nix puts on PATH instead of silently downloading a `python-build-standalone` binary from GitHub into `~/.local/share/uv/python/`. Nix stays the single source of truth for the interpreter; uv is reduced to package resolution, lockfile, and venv management. If nix's `python3` is too old for `requires-python` in `pyproject.toml`, uv fails loudly — that is the correct failure mode (better than a silent fallback that leaks a non-nix interpreter into the project).

Because of this coupling, remember to relax `requires-python` in any copied `pyproject.toml` so it matches whatever major version the current `nixpkgs-25.11-darwin` channel ships as `python3` (typically 3.13 in late 2025).

### TeX: `flake.lock` is checked in on purpose

`templates/tex/` is the only template that ships a `flake.lock`. TeX Live output is sensitive to package versions — a tlpdb update can silently change typeset output or break `chktex` / `tex-fmt` — so TeX projects pin to an exact `nixpkgs` commit rather than a branch ref. Note that the tex template tracks `nixpkgs-unstable` (not `nixpkgs-25.11-darwin` like the others) because TeX Live updates land on unstable first; the lock is what makes "unstable + reproducible" coherent.

This skill's `templates/tex/flake.lock` mirrors `~/dev/tex/shigyo/flake.lock`. If you ever run `nix flake update` in `shigyo`, re-copy its `flake.lock` here so freshly-initialized TeX projects stay aligned with the primary one.

## .envrc

Copy the template from `<this skill's directory>/templates/envrc` to `./.envrc`.

The template is exactly one line: `use flake`. Rationale: the devShell in `flake.nix` is the single source of truth for PATH and env. Adding `dotenv`, `PATH_add`, or inline exports to `.envrc` fragments that truth — a week later you will not remember whether a var came from flake or envrc, and reproducing the env elsewhere means diffing two files.

If the project genuinely needs secrets, put them in a separate `.env` (ignored) and add a single `dotenv .env` line. Keep the shell definition in flake regardless.

## Ignore Rules

Add the direnv cache and nix build outputs to the repo's ignore file:

    .direnv/
    result
    result-*

`.direnv/` is direnv's per-project cache (env dumps derived from nix). `result*` are symlinks created by `nix build`. jj-managed repos read `.gitignore` by default, so a single `.gitignore` covers both.

## Phase 2: Language Init

After `direnv allow` and a clean `cd` into the repo, hand off to the language-specific reference. Each ref owns its own steps, non-obvious rationale, first-run checks, and language-specific anti-patterns.

| Project type | Reference | Downstream skill |
| --- | --- | --- |
| Python (uv) | `references/lang-python.md` | `python-style` |
| TypeScript / Node (pnpm) | `references/lang-typescript.md` | — |
| Rust | `references/lang-rust.md` | — |
| TeX / LaTeX | `references/lang-tex.md` | — |
| Unlisted languages | `references/lang-fallback.md` | — |

Read only the ref that matches the project's primary language — the files are intentionally standalone so Phase 2 loads one language's context, not all of them.

## Anti-Patterns

- Running `uv init` / `pnpm init` on the host shell before `direnv allow` → host toolchain leaks into the project.
- Adding project-only tooling to `~/dotfiles/nix/home/default.nix` → bloats the global user env; keep project tooling in the project's own flake.
- Running `darwin-rebuild switch` after editing a project's `flake.nix` → unnecessary. `darwin-rebuild` only reads `~/dotfiles/flake.nix` + the nix-darwin modules.
- Editing files under `.direnv/` by hand → it is a cache; change `flake.nix` instead and let direnv rebuild it on next `cd`.

## Verification

After step 3, `cd` into the repo should print:

    direnv: loading ~/project/.envrc
    direnv: using flake
    direnv: export ~PATH ...

If nothing happens:

1. `direnv status` — is direnv blocked or not hooked into the shell?
2. Did `direnv allow` succeed? (it hashes the current `.envrc`)
3. Does the flake evaluate? `nix develop --command env | head`
