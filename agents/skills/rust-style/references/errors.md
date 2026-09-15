# Error Handling

- Use `anyhow::Result` at application and CLI orchestration boundaries where errors are reported to humans and callers do not branch on error categories.
- Use concrete error types when callers or tests need to distinguish failure categories.
- `thiserror` is appropriate for deriving concrete error types. Do not introduce it just to wrap every possible failure.
- Add context at I/O, external command, parse, and config boundaries.
- A low-level error such as "No such file or directory" must include the operation and path.
- Use `?` for propagation.
- Do not use `unwrap` or `expect` in production code except for impossible states justified by a nearby invariant.

## Panic Policy

- Use `Result` for expected failures.
- Reserve `panic!` for logic bugs and impossible states.
- Avoid direct indexing when missing data is a normal possibility; use `get()` or explicit validation.
- Public APIs that can panic must document `# Panics`.
- Do not leave `todo!`, `unimplemented!`, or debugging `panic!` calls in production code.
- Use `unreachable!` only when the type system or previous validation makes the branch impossible.

Application-boundary error:

```rust
use anyhow::{Context, Result};

pub fn read_config(path: &Path) -> Result<String> {
    std::fs::read_to_string(path)
        .with_context(|| format!("failed to read config file {}", path.display()))
}
```

Distinguishable domain error:

```rust
#[derive(Debug, thiserror::Error)]
pub enum ProviderError {
    #[error("unknown provider: {0}")]
    UnknownProvider(String),
}
```
