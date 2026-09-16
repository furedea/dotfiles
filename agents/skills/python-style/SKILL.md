---
name: python-style
description: >
    User-specific conventions for designing, writing, testing, and reviewing code in existing
    Python projects. Initial project scaffolding belongs to nix-dev-init.
---

# Python Coding Style Guidelines

## Scope

This skill governs **code written inside an already-bootstrapped Python project** — class design, test authoring, refactoring, code review, naming, imports, docstrings.

Requested project initialization or Nix environment setup belongs to `nix-dev-init`. Apply these
development conventions once the project's selected Python environment and required dependencies
are usable. Routine Python edits do not authorize introducing Nix or changing GitHub settings;
preserve the existing environment workflow.

## Task-Specific References

| Task                                                           | Read                                            |
| -------------------------------------------------------------- | ----------------------------------------------- |
| Dependencies, source layout, tool commands, or type checking   | [Project tooling](references/tooling.md)        |
| Classes, Value Objects, enums, or construction boundaries      | [Models and construction](references/models.md) |
| Writing, running, or reviewing tests                           | [Testing](references/testing.md)                |
| Functions, naming, imports, formatting, logging, or docstrings | [Code conventions](references/code_style.md)    |

Read only the references relevant to the current task. For a focused review, use the references
for the affected concepts.
