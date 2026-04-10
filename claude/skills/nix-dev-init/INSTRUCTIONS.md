# Nix Dev Init Workflow

## Scope

Setting up a **per-project** dev environment — not global dotfiles. For home-manager / nix-darwin edits on `~/dotfiles`, use the `nix-dotfiles` skill instead.

## Mandatory Order

1. `flake.nix` — write the devShell with the language toolchain
2. `.envrc` — single line: `use flake`
3. `direnv allow` — trust the .envrc once, per repo
4. Language init — `uv init` / `pnpm init` / `cargo init` / ... **inside the direnv-activated shell**

### Why this order

- **Toolchain before init**: running `uv init` on the host shell first picks up the host's `python3`, whose version leaks into `pyproject.toml`'s `requires-python` and lockfiles. On another machine (or in CI) this silently breaks reproducibility.
- **Commit `.envrc` before `direnv allow`**: direnv's trust state is keyed by file hash. Allowing first and editing after immediately invalidates the allow, forcing a re-allow.

## Base Flake Template

A minimal, language-agnostic starting point lives at:

    <this skill's directory>/templates/flake.nix

It is intentionally a **base only** — not every language works out of the box. Copy it into the project root, then edit `devShells.<system>.default.packages` to add what the project needs.

Do not preemptively generalize to multi-system (`forAllSystems`, `flake-utils`) unless the project actually needs Linux CI. YAGNI.

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

## Language Follow-up

After `direnv allow`, run the language init inside the now-activated shell and then apply the language-specific skill if one exists:

| Language | Next step | Skill |
| --- | --- | --- |
| Python | `uv init`, merge `~/dotfiles/templates/uv/pyproject.toml` | `python-style` |
| Node | `pnpm init`, copy `~/dotfiles/templates/pnpm/pnpm-workspace.yaml`, then copy the starter files you need from `~/dotfiles/templates/pnpm/` | — |
| TypeScript | start from the Node row, then copy `package.json`, `tsconfig.json`, `.oxlintrc.json`, `.oxfmtrc.json`, and `vitest.config.ts` from `~/dotfiles/templates/pnpm/` | — |
| Rust | `cargo init`, merge `~/dotfiles/templates/Cargo.toml` | — |

For languages not listed above, write the flake devShell additions directly and run the language's standard init command. Do not create a template preemptively.

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
