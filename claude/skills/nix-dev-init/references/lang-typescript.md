# Phase 2: TypeScript / Node (pnpm)

Prerequisite: Phase 1 complete with `templates/typescript/flake.nix` (ships `nodejs_22` + `pnpm`). Verify `which node` and `which pnpm` resolve under `/nix/store/` before proceeding.

This ref covers both plain Node and TypeScript. Start from the Node section and then do the TypeScript additions if the project is TS.

All paths below are relative to this skill's directory. The templates store dotfiles without the leading dot (`gitignore`, `oxlintrc.json`, `oxfmtrc.json`) to avoid macOS hidden-file gotchas in the template folder; **rename them back on copy** into the target project.

## Node (pnpm) core steps

1. `pnpm init` — generates a minimal `package.json`.
2. Copy `templates/typescript/pnpm-workspace.yaml` to the project root. Even single-package projects benefit: it lets you later split into packages without reshuffling lockfiles, and keeps `pnpm` consistent with the user's other repos.
3. Copy `templates/typescript/gitignore` to the project root as `.gitignore` (in addition to the `.direnv/` / `result*` lines from Phase 1).

## TypeScript additions

After the Node steps, also copy from `templates/typescript/`:

- `package.json` — merge into the generated one (keep the project name; bring in `devDependencies`, `scripts`, and `"type": "module"` if present).
- `tsconfig.json` — drop in as-is; it encodes the user's chosen module/target.
- `oxlintrc.json` → copy as `.oxlintrc.json` — oxlint config for fast linting.
- `oxfmtrc.json` → copy as `.oxfmtrc.json` — oxfmt config for formatting.
- `vitest.config.ts` — test runner setup.

Then run `pnpm install` to materialize `node_modules/` and `pnpm-lock.yaml`.

## Why pnpm instead of npm / yarn

pnpm's content-addressable store (`~/.local/share/pnpm/store/`) pairs naturally with nix's store model: both deduplicate by hash, both avoid the "works on my machine" problem that flat `node_modules` causes. The user's dotfiles standardize on pnpm, so staying with it means shared cache across projects.

## Why oxlint / oxfmt instead of eslint / prettier

They are Rust-based, orders of magnitude faster than the JS-native equivalents, and the user's dotfiles already pin their configs. Do not swap them out for eslint / prettier unless the project has a concrete reason (e.g., a shared config from upstream).

## Common first-run checks

- `node --version` should print `v22.x` and resolve under `/nix/store/`.
- `pnpm install` should succeed without network access to a non-pnpm registry.
- For TS: `pnpm exec tsc --noEmit` should type-check the starter files cleanly.

## What NOT to do

- Do not add `nodejs` or `pnpm` to `~/dotfiles/nix/home/default.nix`. Project-level pinning is the whole point of Phase 1.
- Do not commit `node_modules/`. pnpm's lockfile + nix's `nodejs_22` pin is what makes the build reproducible.
- Do not mix package managers (npm install + pnpm install in the same repo). pnpm's lockfile format is not interchangeable with npm's.
