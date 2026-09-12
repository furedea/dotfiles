# Repository Creation and Configuration

Use this reference for requested GitHub repository creation or application of the user's standard
repository policy. It does not require Nix environment setup.

## Command Ownership

Use the public `repo` command. In the dotfiles checkout, command behavior is defined by
`github/repo.sh`, `github/create_repo.sh`, and `github/configure_repo.sh`. The policy payloads are
`github/repo_settings.json` and `github/ruleset.json`; inspect these instead of reproducing their
settings here. Use `repo create --help` or `repo configure --help` for current arguments.

If `repo` is unavailable, locate the user's dotfiles checkout and its `github/repo.sh` entry point.
Do not assume a fixed home-directory layout or replace the wrapper with a workflow that skips
its standard configuration.

## New GitHub Repository

1. Establish the target owner/name, visibility, and whether a template is appropriate. Resolve
   missing choices that affect publication or licensing; do not infer them from a language.
   Inspect any license inherited from a template as well as explicit creation options.
2. Use `repo create <owner/name> <visibility> --template <template>` for a supported template,
   or omit `--template` when a bare repository is intended. Supply exactly one supported visibility
   option; the wrapper owns the ghq clone destination, so do not add `--clone` or `--source`.
3. Check the exit status before using the printed destination. Do not use `cd "$(repo create ...)"`
   as a success guard: the outer command can still execute when creation fails.
4. Inspect the clone and local adjustments. The wrapper applies supported manifest-name changes
   and standard GitHub configuration. It installs Lefthook only when its configuration and the
   executable are available; check the outcome instead of assuming installation occurred.
5. Continue to environment setup only when requested. Template renames may leave local changes;
   commit and publication are governed by `git-workflow`, not by creation success.

Creation and configuration are not atomic. If a later stage fails, inspect the remote and clone
before retrying. Report completed stages; do not delete the remote or local files to restart.

## Existing GitHub Repository

Use `repo configure <owner/name>` when applying the full standard repository policy is requested.
Resolve the exact target from the request or verified remote; prefer an explicit owner/name over
the authenticated-user default when working with an existing repository.

This command applies all of the following:

- Repository settings from `github/repo_settings.json`.
- Vulnerability alerts and the dependency graph.
- The common ruleset from `github/ruleset.json`, updating a same-named ruleset or creating it.

Inspect the current policy payloads and relevant remote state before applying them, including
whether the ruleset's branch target and required checks fit the repository. The command is not a
ruleset-only operation and does not create the CI workflows needed to satisfy required checks.
If the request covers only rulesets or conflicts with existing policy, explain the mismatch and
resolve the intended scope before applying the broader command. An explicit request for the full
standard policy does not need repeated authorization for each included step.

Verify the resulting settings through read-only GitHub queries where available. If application or
verification fails, report partial results and remaining work; do not claim the whole policy was
applied. No clone, Nix activation, or source edit is required for configuration alone.
