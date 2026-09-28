# Rust Code Conventions

## Logging and Diagnostics

- Short-lived CLI tools may use `eprintln!` for warnings and progress.
- Libraries must not initialize global logging.
- Use `tracing` only when the project needs structured logs, spans, or long-running diagnostics.
- Keep human diagnostics on stderr and machine-readable command output on stdout.
- Include paths, command names, and config keys in diagnostics when they explain the failure.

## Naming Conventions

- Avoid `manager`, `helper`, `util`, and `common` unless the name is already established locally.

### Module Naming

- Name modules after the domain or action they contain.
- Prefer `render.rs` over `renderer.rs` for module names.
- Prefer `install.rs` over `installer.rs` for module names.
- Prefer `config.rs` over `config_manager.rs` for module names.
- Use `Renderer` or `Installer` as type names only when the type owns behavior.

## Imports

- Group imports as standard library, third-party crates, then local crate modules.
- Let rustfmt sort and format imports when the project enables that behavior.
- Prefer explicit imports over glob imports.
- Use glob imports only in tests or prelude-style modules where the scope is obvious.
- Avoid `as` aliases unless they remove ambiguity or follow a local convention.
- Prefer `crate::` for crate-local imports and `super::` for parent-module test imports.
- Keep trait imports close to the code that needs method resolution.

## Whitespace and Line Breaks

- Let rustfmt make final whitespace and wrapping decisions.
- Use trailing commas in multi-line structs, enums, arrays, match arms, and function calls.
- Break long method chains at semantic boundaries.
- Do not fight rustfmt with manual alignment.
- Keep one blank line between groups of related items when it improves scanning.

## Comments and Documentation

- Comments explain why, not what.
- Prefer clear types, function names, and module boundaries over explanatory comments.
- Public APIs should have doc comments when they are consumed outside the crate.
- Include examples in doc comments only when they should compile as doc tests.
- Use `//!` for module-level documentation.
- Use `///` for item documentation.
- Public fallible functions should document `# Errors` when the error cases are not obvious.
- Public functions that can panic should document `# Panics`.
- Architectural choices, dependency decisions, and external-tool boundary rules belong in ADRs.
- Do not write prose specifications that duplicate tests.
