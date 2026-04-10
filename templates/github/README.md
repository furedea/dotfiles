# GitHub Starter Templates

These files are starter templates for repository automation and security features
that are primarily configured through GitHub Actions.

Copy only the files you need into a target repository:

```sh
mkdir -p .github/workflows
cp ~/dotfiles/templates/github/.github/workflows/*.yml .github/workflows/
cp ~/dotfiles/templates/github/.github/dependency_review_config.yml .github/
```

## Default Adopted Set

These are the tools currently intended as the default set for new repositories.

### CI

- `actionlint`
- `zizmor`
- `Dependency Review`
- `CodeQL`
- `release-please`

### GitHub-side Settings

- `Renovate`
- `Push Protection`
- `Secret Scanning`
- `Rulesets`

These are part of the default adopted set, but they are configured in GitHub
settings or through a GitHub App, so there are no workflow template files for
them in this directory.

## Optional

- `artifact attestation`
  - Add this only for repositories that build and publish artifacts from GitHub
    Actions.
  - It is intentionally excluded from the default set because it depends on the
    repository's concrete build and release flow.

## Included Workflows

- `gha_hygiene.yml`
  - Runs `actionlint` and `zizmor` for GitHub Actions workflow hygiene.
- `dependency_review.yml`
  - Blocks pull requests that introduce vulnerable dependencies above the
    configured severity threshold.
- `codeql.yml`
  - Runs CodeQL on pull requests, pushes to `main`, and on a weekly schedule.
  - Edit the language matrix before enabling it.
- `release_please.yml`
  - Opens and updates release PRs from Conventional Commits.
  - Replace `release-type: simple` with a repo-specific strategy when needed.

## GitHub-side Features Not Represented As Workflow Files

These are still recommended, but they are configured in repository or
organization settings instead of living in `.github/workflows/`.

- Renovate
  - Prefer the GitHub App or a self-hosted bot plus a `renovate.json` config.
- Push Protection
- Secret Scanning
- Rulesets

## Build-specific Feature Not Templated Here

- Artifact attestation
  - This depends on the repository's build and release pipeline, so it is
    better added together with the actual build workflow instead of as a
    generic standalone template.
