# Rust Package Design

## Cargo Features

- Keep feature flags additive. Enabling a feature should not remove behavior.
- Avoid growing default features unless the behavior is truly the default user expectation.
- Keep optional dependency features named clearly after the capability they enable.
- Test important feature combinations explicitly.
- Consider `cargo test --all-features` when features affect compiled code paths.
- Do not use features as a runtime configuration substitute.

## Public API Design

- Reserve `pub` for APIs intended to be consumed outside the crate.
- Use `pub(crate)` for items shared across internal modules, including inside private modules when it clarifies that the item is not an external API.
- Keep items private when they are only used inside the current module.
- Keep public APIs smaller than internal APIs.
- Avoid exposing third-party types in public APIs unless that dependency is part of the intended API.
- Use `#[non_exhaustive]` for public enums or structs that may need new variants or fields.
- Seal traits that downstream crates should not implement.
- Treat new public trait implementations as semver-relevant changes.
- Do not expose mutable internal collections directly.

## Macro and Build Script Policy

- Prefer functions, traits, and generics before macros.
- Add a macro only when it removes repetition that ordinary Rust abstractions cannot express clearly.
- Avoid procedural macros unless the project has a strong reason for compile-time code generation.
- Keep test helper macros small and obvious.
- Do not add `build.rs` until native linking, environment probing, or code generation is actually required.
- Generated code should have tests or snapshots that make the generated output reviewable.
