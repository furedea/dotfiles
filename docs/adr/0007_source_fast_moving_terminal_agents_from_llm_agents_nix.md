# ADR-0007: Source fast-moving terminal agents from llm-agents.nix

- Status: Accepted
- Date: 2026-08-23
- Supersedes: ADR-0006

In the context of keeping fast-moving terminal agents reproducible, facing a dedicated Herdr pin
that lagged both upstream and `llm-agents.nix`, we decided for sourcing exactly Claude Code, Codex,
and Herdr from `numtide/llm-agents.nix` and against retaining the dedicated Herdr flake or using the
older nixpkgs package, to centralize timely updates without installing the catalog wholesale,
accepting that all three tools now share one package source and lock-file update boundary.
