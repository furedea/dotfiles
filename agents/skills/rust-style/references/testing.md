# Rust Testing

Use `tsdd` to decide when to add or reuse tests, which behavior to cover, and the appropriate
verification level. The conventions below govern Rust test tooling and structure.

- Use `cargo test` as the default test command.
- Write unit tests in the target source file or module with `#[cfg(test)] mod tests`.
- Use `tests/*.rs` for integration tests that exercise public APIs or CLI behavior.
- Integration tests compile as a separate crate and should use only public APIs.
- Use doc tests for public examples that should stay compilable.
- Use temporary directories for filesystem tests. Do not touch the real home directory.
- Snapshot generated artifacts only when exact output is part of the behavior.
- Keep snapshots small and focused.
- Prefer fake implementations behind traits over broad mocking libraries.
- Use table-driven tests for the same behavior across multiple inputs.
- Use async tests only when the project already has an async runtime requirement.

## Test Structure

- **Unit test**: place next to the implementation in the same file or module.
- **Integration test**: place under `tests/` when testing public API, CLI behavior, or crate-level wiring.
- **Helper function**: prefer local helper functions when setup is lightweight or argument-driven.
- **Shared fixture**: keep it in the test module first; move to `tests/common/` only when multiple integration test files need it.
- **Fake implementation**: prefer explicit fake types over global mocks.
- **Parameterized cases**: use a table of cases and loop over it when one behavior has many inputs.

Example unit test layout:

```rust
pub fn normalize_name(input: &str) -> String {
    input.trim().replace('_', "-")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_name_trims_whitespace_and_replaces_underscores() {
        assert_eq!(normalize_name(" rust_style "), "rust-style");
    }
}
```
