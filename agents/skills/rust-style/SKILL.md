---
name: rust-style
description: >
    User-specific conventions for designing, writing, testing, and reviewing code in existing
    Rust projects. Initial project scaffolding belongs to project-setup.
---

# Rust Coding Style Guidelines

## Scope

This skill governs code written inside an already-bootstrapped Rust project: package commands, module layout, test authoring, refactoring, code review, naming, ownership, errors, filesystem operations, comments, and docs.

Requested project initialization or Nix environment setup belongs to `project-setup`. Apply these
development conventions once the project's selected Cargo/Rust toolchain and required dependencies
are usable. Respect the existing toolchain-management policy; routine Rust edits do not authorize
introducing Nix, creating a competing toolchain definition, or changing GitHub settings.

## Task-Specific References

| Task                                                                    | Read                                                           |
| ----------------------------------------------------------------------- | -------------------------------------------------------------- |
| Dependencies, source layout, formatting tools, or verification commands | [Project tooling](references/tooling.md)                       |
| Types, constructors, ownership, conversions, or collections             | [Types and ownership](references/types.md)                     |
| Writing, running, or reviewing tests                                    | [Testing](references/testing.md)                               |
| Fallible operations, error types, or panic boundaries                   | [Error handling](references/errors.md)                         |
| CLI parsing and execution                                               | [CLI code](references/cli.md)                                  |
| Filesystem operations                                                   | [Filesystem operations](references/filesystem.md)              |
| Configuration or serialization                                          | [Config and serialization](references/config_serialization.md) |
| Cargo features, public APIs, macros, or build scripts                   | [Package design](references/package_design.md)                 |
| Naming, imports, formatting style, logging, or documentation            | [Code conventions](references/code_style.md)                   |

Read only the references relevant to the current task. For a focused review, use the references
for the affected concepts.
