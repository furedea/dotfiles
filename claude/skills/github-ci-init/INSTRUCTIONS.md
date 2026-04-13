# GitHub CI Init Workflow

## Scope

This skill owns the **initial scaffolding** of GitHub Actions CI for a repository — which workflow files ship, where they go, and when to skip CI entirely.

It does NOT own **writing or editing the YAML contents of individual workflow files** — that belongs to the `gha-style` skill (permissions minimization, action version pinning, script injection prevention, etc.).

## When to apply vs skip

Not every project benefits from the default set. Applying it to a throwaway repo creates maintenance noise (CodeQL alerts, dependency review blocks on every PR, release-please commits) that outweighs the payoff.

### Apply when

- The project has a plausible long-term lifetime (weeks to years)
- PRs are expected (from others, or from yourself via feature branches)
- Dependency vulnerability monitoring is worth having
- The project is public, or likely to become public

### Skip when

- It's a throwaway experiment, tutorial follow-along, or one-off script
- The project lives in a single commit and won't be touched again
- It's a scratch space for exploring a library

When in doubt, **skip**. CI can always be added later by running this skill again on the existing repo — that is exactly the retrofit case it is designed for.

## The default adopted set

See `references/default-set.md` for the full rationale: what each shipped workflow does, which GitHub-side features (Renovate, Push Protection, Secret Scanning, Rulesets) are recommended but not templated here because they live in repo/org settings, and what is intentionally excluded from the default (e.g. artifact attestation).

## Steps

1. **Confirm the project passes the "apply" criteria**. If it does not, stop and explain why CI would be net-negative for this project.
2. **Create `.github/workflows/`** in the project root if it does not already exist.
3. **Copy the workflow files** from `templates/` (in this skill's directory) into the project's `.github/workflows/`:
   - `gha_hygiene.yml` — runs `actionlint` and `zizmor` on every PR; ship in every repo.
   - `dependency_review.yml` — blocks PRs that introduce vulnerable dependencies above a severity threshold; ship in every repo.
   - `codeql.yml` — runs CodeQL on push/PR/weekly; ship in every repo, **but edit the language matrix** before committing (the template is language-agnostic and will no-op until the matrix matches the project's languages).
   - `release_please.yml` — opens release PRs from Conventional Commits; ship when the project will have versioned releases. **Replace `release-type: simple`** with a repo-specific strategy (e.g. `python`, `node`, `rust`) if needed.
4. **Copy** `templates/dependency_review_config.yml` into the project's `.github/`.
5. **Remind the user** about the GitHub-side features not templated here (Renovate / Push Protection / Secret Scanning / Rulesets). These live in repo or org settings, not in `.github/workflows/`, so this skill cannot install them. Point at `references/default-set.md` for the short-list.

## Handoff to `gha-style`

After copying, any edit to the resulting `.github/workflows/*.yml` — changing triggers, tuning `permissions:`, adding a job, pinning an action version, fixing an `actionlint` warning, responding to a `zizmor` finding — belongs to the `gha-style` skill.

This split is deliberate:

- `github-ci-init` owns the **"which files exist"** decision. It is a one-shot, per-repo scaffolding action.
- `gha-style` owns the **"how each file is written"** decision. It is an ongoing code-review loop every time a workflow is touched.

Duplicating either side into the other would let the two drift. Keep them separate and chain them: scaffold with this skill, then edit with `gha-style`.

## Anti-patterns

- **Applying the full default set to a throwaway experiment**. CodeQL/dependency review/release-please on a 1-commit repo is pure maintenance noise.
- **Editing workflow YAML inside this skill's flow**. Redirect to `gha-style`. Even "just tuning one permission" should go through that skill so the conventions stay consistent.
- **Copying `references/default-set.md` into the project**. It is documentation of this skill, not project content.
- **Skipping the CodeQL language-matrix edit** in step 3. Committing the unmodified template means CodeQL silently never runs anything.
