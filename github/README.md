# GitHub repository setup

Standard repo settings and branch ruleset that `setup_repo.sh` applies to a new GitHub repository.

## Files

| File | Purpose |
| --- | --- |
| `repo_settings.json` | Squash-only merges, auto-merge, delete branch on merge |
| `ruleset.json` | `main` branch protection: PR required, linear history, no force-push, `all-green` status check |
| `setup_repo.sh` | Idempotent applier: `./setup_repo.sh <owner>/<repo>` |

## Required `all-green` status check

`ruleset.json` requires a status check named `all-green` on PRs into `main`. Every project template under `dev/templates/template-*` defines an `all-green` job in `.github/workflows/ci.yml` that aggregates the rest of the CI jobs via `needs:` and fails if any prerequisite did not succeed. Repos generated from those templates inherit this job, so PRs can merge after `setup_repo.sh` runs.

When adding a new CI job, also add it to the `needs:` list of `all-green` in the same `ci.yml`. The ruleset itself does not need to change.

## Caveat: do not apply this ruleset to this dotfiles repo or the template repos themselves

The dotfiles repo and the `template-*` repos run a **relaxed variant** of `main protection` configured manually in the GitHub UI:

- `deletion`, `non_fast_forward`, `required_linear_history` only
- No `pull_request` rule, no `required_status_checks` rule

This intentionally allows direct push to `main` for low-friction maintenance. Running `setup_repo.sh` against these repos would overwrite the ruleset with the stricter version in `ruleset.json` and lock out direct push. `setup_repo.sh` is intended for downstream repos generated from the templates, not for the templates themselves.
