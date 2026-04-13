# Phase 2: Rust (cargo)

Prerequisite: Phase 1 complete with `templates/rust/flake.nix` (ships `cargo`, `rustc`, `rustfmt`, `clippy`). Verify `which cargo` and `which rustc` resolve under `/nix/store/` before proceeding.

## Steps

1. `cargo init` — generates `Cargo.toml`, `src/main.rs` (or `src/lib.rs` with `--lib`), and an initial `.gitignore`.
2. Merge `templates/rust/Cargo.toml` (in this skill's directory) into the generated `Cargo.toml`. Keep the generated `[package]` name/version; bring in `[profile.*]`, `[lints.*]`, and any shared dependency pins from the template.
3. Ensure the project `.gitignore` also has `.direnv/` and `result*` from Phase 1 (cargo's generated `.gitignore` only covers `/target`).
4. `cargo build` — confirms the nix-provided `rustc` + `cargo` chain works end to end.

## Why not `rust-overlay` / `fenix` by default

The user's default Rust template uses nixpkgs' `cargo` + `rustc` (currently stable, roughly matching what `nixpkgs-25.11-darwin` ships). This is deliberate:

- Nixpkgs stable is good enough for 95% of projects and avoids an extra flake input.
- `rust-overlay` / `fenix` add a significant first-build cost (the toolchain derivation is large) and lock you to a fresh evaluation every time.
- When a project genuinely needs a specific toolchain channel or nightly feature, add `rust-overlay` as a one-off project exception — not a default.

## LSP / rust-analyzer

Do **not** add `rust-analyzer` to the devShell. The globally-installed `rust-analyzer` (from `~/dotfiles`) discovers the project's toolchain via `rustc --print sysroot`, and because direnv has put the nix-store `rustc` on PATH, the global LSP automatically uses the correct sysroot per project. Adding a per-project `rust-analyzer` bloats the closure for no benefit.

## Common first-run checks

- `cargo --version` and `rustc --version` should print versions matching `nixpkgs-25.11-darwin`.
- `cargo build` should succeed on the starter `main.rs`.
- `cargo clippy` should run without needing extra installs.

## What NOT to do

- Do not add `cargo` / `rustc` to `~/dotfiles/nix/home/default.nix`. Per-project pinning is the whole point.
- Do not commit `target/`. It is a machine-specific build cache.
- Do not run `rustup` inside the direnv shell. Nix owns the toolchain; rustup would install a second one into `~/.rustup/` and silently shadow it via `cargo`'s PATH lookup.
