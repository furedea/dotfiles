---
name: nix-dev-init
description: >
    Per-project development environment bootstrap workflow for this user: ghcreate --template → direnv allow → language sync/build **inside the direnv-activated shell**. ALWAYS load when starting a new project, initializing a repo, scaffolding dev tooling, or writing project-level flake.nix / .envrc / devShell. This skill is DISTINCT from `nix-dotfiles` (which covers global dotfiles system config under ghq) — load THIS one for project-scoped devShells. Without this skill, Claude will run `pnpm install` / `cargo build` on the host shell and leak the host toolchain version into lockfiles, silently breaking reproducibility. All supported languages have GitHub template repos under furedea/ (template-python, template-typescript, template-rust, template-tex, template-minimal) used via `ghcreate --template`. Also trigger on "/nix-dev-init", "new project", "set up dev environment", or any mention of creating a flake.nix for a project.
---

Read `INSTRUCTIONS.md` (in this skill's directory) for the full workflow and template repo pointers before proceeding.
