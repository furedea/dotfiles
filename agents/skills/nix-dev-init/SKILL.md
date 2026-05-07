---
name: nix-dev-init
description: >
    Per-project development environment bootstrap workflow for this user: ghcreate --template → direnv allow → language sync/build inside the direnv-activated shell. ALWAYS load when starting a new project, initializing a repo, scaffolding dev tooling, or writing project-level flake.nix / .envrc / devShell. Also load when the user asks to use or reference template-python, template-typescript, template-rust, template-tex, template-minimal, or configure an existing project from a template. This skill is DISTINCT from `nix-dotfiles` (global dotfiles system config under ghq); load THIS for project-scoped devShells. Without it, Claude or Codex may run language tools on the host shell and leak host toolchain versions into lockfiles. Supported language templates live under furedea/ and are used via `ghcreate --template`. Also trigger on "/nix-dev-init", "new project", "set up dev environment", or any mention of creating a flake.nix for a project.
---

Read `INSTRUCTIONS.md` (in this skill's directory) for the full workflow and template repo pointers before proceeding.
