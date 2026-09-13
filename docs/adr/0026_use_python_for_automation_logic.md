# ADR-0026: Use Python for automation logic

- Status: Accepted
- Date: 2026-09-13

In the context of personal hooks and command helpers handling structured input, policy decisions,
process execution, and persistent state, facing shell implementations that couple these decisions
to pipelines and process-level fixtures, we decided for standard-library Python modules with
pytest for internal contracts, shell code and Bats for shell integration, and explicit Nix checks
for declarative configuration, and against shell-centric application logic or a wholesale rewrite
in a compiled language, to make decisions directly testable while retaining real integration
evidence, accepting a Nix-managed Python runtime as a deployment dependency. External Python
runtime packages require a concrete need that the standard library or existing system tools
cannot reasonably satisfy; development-only verification tools remain separate dependencies.

Shell remains appropriate for parent-shell state, thin executable adapters, and lifecycle
launchers whose main contract is process execution. Existing command names remain stable.
The supplementary command guards inspect shfmt's syntax tree, reject unsupported dynamic
syntax, and preserve existing POSIX ERE and PCRE2 policy dialects through grep and ripgrep.
They do not replace the provider's permissions or sandbox boundary.
