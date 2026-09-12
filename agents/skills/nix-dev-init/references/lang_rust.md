# Rust / Cargo Setup

Use after [development environment setup](dev_environment.md). The default for new projects is
`furedea/template-rust`; existing projects retain their manifest, workspace, and toolchain policy.

## Setup and Verification

1. Inspect `Cargo.toml`, any workspace configuration, lock, and toolchain requirements. Reuse
   existing source; use `cargo init` only when initial Cargo scaffolding is actually missing.
2. Verify Cargo and rustc versions and executable locations inside the project environment.
   Confirm required components such as rustfmt and Clippy are available from the intended toolchain.
3. Run the relevant project build inside that environment, such as `direnv exec . cargo build`,
   when equivalent successful evidence is not already available. Preserve the language lock and
   inspect necessary changes resulting from template renames or manifest edits.
4. Once the toolchain and required dependencies work, hand off to `rust-style`.

## Toolchain Ownership

Prefer nixpkgs' Cargo and rustc for a new Nix-managed project when they satisfy its requirements.
This avoids an extra flake input. Add an overlay or another toolchain source only for a concrete
need such as a specific release, nightly feature, or target.

Do not create `rust-toolchain.toml` merely because the project uses Rust. If an existing project
uses that file or rustup, respect its requirements and make the intended Nix integration explicit;
do not silently replace its toolchain policy. For a Nix-owned toolchain, do not install a competing
rustup toolchain to bypass a failure.

For rust-analyzer issues, apply the editor guidance in the environment reference and check the
effective sysroot and component compatibility. Keep `target/` out of version control.
