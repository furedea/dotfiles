# ADR-0024: Manage language runtimes with Nix

- Status: Accepted
- Date: 2026-09-12

In the context of needing Python, Node.js, and Rust both for project work and occasional host-shell
commands, facing mutable runtime installations from uv and rustup that cannot be reproduced from a
flake lock, we decided for Nix-managed global fallback runtimes and independently pinned project
devShell toolchains, with uv, pnpm, and Cargo responsible for language dependencies, and against
activation hooks that download runtimes into the home directory, to make each environment
reproducible while keeping convenient host-shell commands, accepting duplicate Nix store closures
when global and project versions differ.
