# TypeScript / Node Setup

Use after [development environment setup](dev_environment.md). The default for new projects is
`furedea/template-typescript` with pnpm. Preserve an existing project's package-manager choice
unless migration is requested.

## Setup and Verification

1. Inspect `package.json`, its scripts and package-manager declaration, the lock, and the devShell.
   Verify effective Node and package-manager versions against those definitions, not a version
   copied into this reference.
2. Reuse the manifest, source, and tooling configuration. Initialize only missing project files;
   do not run `pnpm init` when the manifest already exists.
3. In the project environment, run `pnpm install` for pnpm projects. Preserve the existing lock
   and configured registries; inspect necessary lock changes rather than upgrading dependencies.
4. Confirm the installed dependencies support the project's actual scripts. Reuse hook results
   for lint, format, typecheck, and tests; use a targeted check if required evidence is missing.

## Defaults and Boundaries

- pnpm is the user's new-project default and shares a content-addressed dependency cache.
  Reproducibility still depends on the toolchain, lock, and installation settings.
- Keep the template's oxlint/oxfmt setup unless the project has a concrete reason to use different
  tooling, such as existing upstream conventions. Do not scaffold competing configurations.
- Do not mix package managers or introduce a second lock format during environment setup.
- Do not commit `node_modules/`; retain the project toolchain definition and language lock.
