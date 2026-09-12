# Other Languages

Use after [development environment setup](dev_environment.md) when no dedicated language reference
matches. `furedea/template-minimal` provides shared tooling for new projects; add the needed
language toolchain without removing those shared tools.

## Setup and Verification

1. Identify the runtime/compiler, package manager, and required quality tools from the project's
   requirements and conventions. Resolve package names against its chosen nixpkgs input.
2. Add missing tools to the project devShell. Prefer available packages over speculative overlays.
3. Reload the project environment and verify the effective tools as described in the environment
   reference. Do not use global fallback availability as proof the devShell is complete.
4. Run the language's supported initialization command only for missing scaffolding, inside the
   project environment. For existing projects, use their dependency sync/build entry points.
5. Add missing language cache/build ignore entries and obtain a minimal successful smoke result.
   Follow relevant language conventions for subsequent development.

## Repeated Setup Patterns

Do not create a new template for the first use of a language. If several projects demonstrate a
stable reusable pattern, propose a separate template-maintenance task: derive from the minimal
template, add the language environment and conventions, and extend name substitution only when
needed. Reuse the common repository policy; do not invent language-specific ruleset files.
Add a `lang_<name>.md` reference and update the routing table if a dedicated workflow becomes useful.

Keep throwaway environment experiments distinct from durable project setup; a temporary Nix shell
does not replace the declared toolchain and lock for a project intended to be reproducible.
