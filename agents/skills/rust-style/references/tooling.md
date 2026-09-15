# Rust Project Tooling

## Package Management

- Use Cargo for Rust package operations.
- Add dependencies with `cargo add <crate>` when `cargo add` is available.
- Add development dependencies with `cargo add --dev <crate>`.
- Use `cargo check` for a fast compile/type-check pass when tests are not needed yet.
- Use `cargo test` for the default verification pass.
- Use `cargo clippy --all-targets -- -D warnings` for linting.
- Do not edit `Cargo.lock` manually.
- Commit `Cargo.lock` for applications, CLI tools, and internal tools.
- For library crates, follow the repository's existing `Cargo.lock` policy.
- Do not use `@latest`-style version shortcuts in documentation or committed commands.
- Do not add a dependency only because it is common. Add it when it removes real boundary complexity or prevents error-prone code.

## Directory Structure

- Follow Cargo's standard layout.
- Store production code in `src/`.
- Keep `src/main.rs` thin for binary crates. It should parse CLI arguments and call library code.
- Put reusable execution logic in `src/lib.rs` and focused modules under `src/`.
- Store integration tests in `tests/`.
- Keep unit tests near the module when they need private access.
- Use `examples/` only for runnable examples that should compile.
- Avoid `utils.rs` and `helpers.rs`; name modules by domain or action.

Typical binary crate shape:

```text
src/
├── main.rs
├── lib.rs
├── cli.rs
├── config.rs
├── fs_ops.rs
└── render.rs
tests/
└── cli.rs
```

## File Standards

- Let `rustfmt` define formatting. Do not hand-format around rustfmt.
- Keep files focused and cohesive.
- Prefer modules of roughly 200-500 lines. Split when multiple responsibilities appear.
- Keep public items before private helpers when it improves scanning.
- Use `mod.rs` only when the existing project already uses that style; otherwise prefer `module_name.rs` plus `module_name/child.rs`.
- Put one top-level concept per file when the concept has real behavior.
- Keep generated code out of hand-written modules unless the project has a clear generated-code convention.

## Quality Gates

Confirm the relevant verification results before finishing Rust changes. Follow `tsdd`'s Automatic
Verification policy for execution needs and reuse of successful hook evidence. The default commands
are below; use the project's stricter gate when defined:

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

- Forbid `unsafe` by default.
- Do not enable broad lint sets such as `clippy::pedantic` at project start.
- Add targeted lint configuration only when it catches mistakes the project actually cares about.

Recommended package-level guard:

```toml
[lints.rust]
unsafe_code = "forbid"

[lints.clippy]
dbg_macro = "deny"
todo = "deny"
unimplemented = "deny"
```
