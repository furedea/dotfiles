# ADR-0006: Consolidate primary agents in llm-agents.nix

- Status: Superseded
- Date: 2026-08-23

In the context of keeping fast-moving Claude Code and Codex releases reproducible, facing duplicate
special-purpose flake inputs and a broad catalog of unrelated tools, we decided for sourcing only
Claude Code and Codex from `numtide/llm-agents.nix` and against retaining the dedicated inputs or
installing the catalog wholesale, to centralize updates without expanding the installed tool or
trust surface, accepting that both primary agents now advance through one lock-file input update.
