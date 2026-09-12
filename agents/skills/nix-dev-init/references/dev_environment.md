# Project Development Environment

Use this reference for new or existing projects, including local-only projects. GitHub creation
and standard remote settings are optional, separate operations.

## Inspect and Adapt

Inspect the target project's environment definitions, manifests, lockfiles, supported platforms,
CI, and hook configuration. For an existing project, preserve its conventions and introduce only
the requested Nix integration; do not rerun language initialization over existing manifests.
For a new project, reuse the selected template before creating missing files.

- Define the complete project toolchain and non-secret environment in the project's devShell.
  Global fallback runtimes can remain installed but are not substitutes for project declarations.
- Use the project's pinned package set to select packages. Do not hard-code template versions in
  instructions or assume a global flake registry resolves to the same nixpkgs revision.
- Preserve `flake.lock` and language lockfiles. Create missing locks when needed; update existing
  entries only for an intentional dependency or environment change, and inspect the resulting diff.
  Do not synchronize locks with unrelated projects or templates during setup.
- Support the platforms actually required by development and CI. Do not add multi-system helpers
  or extra flake inputs speculatively.
- Keep `.envrc` minimal (`use flake` for a new Nix-only setup). Preserve existing integrations when
  adopting Nix into a project. Avoid duplicating toolchain paths or versions there.
- Keep secrets outside Nix expressions and the store. When needed, use ignored local secret files
  and the project's loader, such as `dotenv .env`; do not print their contents for diagnostics.
- Ensure ignore rules cover `.direnv/`, `result`, `result-*`, and language-specific caches without
  replacing existing ignore rules. Never edit `.direnv/` as configuration.

Git is not a prerequisite for evaluating a local flake. In a Git-backed flake, new source files
must be visible to Nix through Git tracking; stage only the relevant files when needed, respecting
existing staging. Neither flake evaluation nor direnv trust requires a commit.

## Activate Before Language Setup

1. Review `.envrc` and the setup code it invokes before authorizing it with `direnv allow`.
   Re-authorize if its approved contents change; do not automatically trust unreviewed code.
2. Run language commands in the project directory with `direnv exec . <command>`, or in a shell
   whose project environment is demonstrably active. Do not assume `direnv allow` or `cd` activates
   the environment in an agent's non-interactive shell or carries it across separate tool calls.
3. Use `nix develop --command <command>` when only the flake environment is required, including
   diagnosis without direnv. It does not load additional `.envrc` integrations or secret loaders.
4. After changing the flake, reload and confirm the new environment is in use. Investigate stale
   or fallback environments rather than continuing with an old toolchain after evaluation fails.

Project flakes do not require `darwin-rebuild switch` or Home Manager activation. Do not install
missing project tools globally or through a second toolchain manager to bypass setup failures.

## Verify the Effective Environment

Inside the selected environment, check required tool versions and executable locations against
the project definition and lock. A `/nix/store/` path alone is insufficient: global tools are also
Nix-managed. Confirm tools are declared in the project and investigate any path/version mismatch;
use the corresponding language reference for dependency-environment checks.

When loading fails, inspect `direnv status`, trust status, and the flake evaluation error. Use a
targeted command such as `nix develop --command <tool> --version`; do not dump the environment.
Use the project's actual sync/build entry point for a minimal smoke check and reuse successful
hook evidence as described in the main skill.

## Editor Tooling

Prefer the existing global editor/LSP installation instead of adding every LSP to every devShell.
Environment inheritance, interpreter discovery, sysroots, and version compatibility still need
checking when an editor issue occurs; automatic discovery is not a guarantee. Add project-local
editor tooling when a concrete compatibility requirement justifies it.
