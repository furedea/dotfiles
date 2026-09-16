# Types and Ownership

## Module Item Order

- Put module-level constants before types when they configure the following code.
- Prefer `type` aliases and enums before structs that use them.
- Put public structs, enums, and traits before their implementations.
- Put public functions before private helper functions.
- Keep `#[cfg(test)] mod tests` at the bottom of the file.
- Keep related types and their `impl` blocks close together.

## Structs

- Derive `Debug` for most domain structs.
- Derive `Clone`, `PartialEq`, `Eq`, `Ord`, or `Hash` only when the type actually needs that capability.
- Keep fields private when the type has invariants.
- Use constructors for types with validation or normalization.
- Use tuple structs for narrow newtypes and named-field structs when field names improve clarity.
- Avoid boolean constructor arguments; prefer an enum or options struct.

Value Object pattern:

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SkillName(String);

impl SkillName {
    pub fn parse(value: impl Into<String>) -> anyhow::Result<Self> {
        let value = value.into();
        if value.is_empty() {
            anyhow::bail!("skill name must not be empty");
        }
        Ok(Self(value))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}
```

## Enums

- Use enums for fixed states, providers, modes, and policy decisions.
- Convert user input strings into enums at the boundary.
- Avoid passing raw string modes through the codebase.
- Prefer exhaustive `match` statements for domain control flow.
- Implement `Display` when the enum has a stable user-facing representation.
- Implement `FromStr` or `TryFrom<&str>` when parsing user input.

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Provider {
    Claude,
    Codex,
}
```

## Functions and Methods

- Keep functions focused and small.
- Prefer borrowing in parameters: `&str`, `&Path`, `&[T]`.
- Return owned values when the function creates or transforms ownership.
- Use associated functions for pure construction.
- Keep I/O in module-level functions or dedicated service structs, not inside Value Object constructors.
- Prefer `Result<T, E>` for expected failures.
- Prefer early returns for guard clauses.
- Avoid `async` unless the project has real concurrency or nonblocking I/O requirements.

## Getter and Conversion Naming

- Borrowed views use `as_*`: `as_str`, `as_path`, `as_slice`.
- Consuming conversions use `into_*`: `into_inner`, `into_path_buf`.
- Cheap copies can use the value name directly: `len`, `status`, `provider`.
- Avoid Java-style `get_*` unless following an existing local convention.
- Boolean queries use `is_*`, `has_*`, `can_*`, or `should_*`.
- Fallible parsing uses `parse`, `try_from`, or `from_str`.

## Ownership and Borrowing

- Accept `impl AsRef<Path>` only at outer convenience boundaries. Inside the codebase, pass `&Path`.
- Accept `impl Into<String>` for constructors that store owned strings.
- Do not clone to satisfy the borrow checker until the ownership model is understood.
- Use `Cow` only when profiling or API shape shows it is worthwhile.
- Prefer slices over `&Vec<T>` in function parameters.

## Collections

- Use `Vec<T>` for ordered sequences.
- Use `BTreeMap` or sorted vectors when deterministic output order matters.
- Use `HashMap` when order is irrelevant and lookup dominates.
- Do not expose mutable collections directly from domain types.

## Strings and Formatting

- Use `&str` for borrowed string input and `String` for owned string storage.
- Use `format!` when constructing a new owned string from values.
- Use captured identifiers in formatting when it improves readability: `format!("{name}")`.
- Prefer `to_owned()` or `String::from` when converting a string literal to `String`.
- Avoid unnecessary `to_string()` in hot or repeated code.
- Keep user-facing text separate from machine-readable output.

## Numeric Conversions

- Use `usize` for indexing and collection lengths.
- Do not use `as` for narrowing integer conversions.
- Use `TryFrom` or `try_into` when a conversion can fail.
- Use newtypes when a number has a domain unit or invariant.
- Make lossy conversions explicit in the function or variable name.
