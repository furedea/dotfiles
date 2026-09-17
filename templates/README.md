# Reference templates

Copy these files into a project and adapt them there. Each project's checked-in configuration
owns its release behavior; changes here do not automatically update existing projects.

## Release workflow

`release_please.yml` combines release management and artifact publication in two jobs. It is
based on [agent-harness's workflow](https://github.com/furedea/agent-harness/blob/main/.github/workflows/release_please.yml).
The former `artifact_attestation.yml` is integrated into this workflow. Remove that standalone
workflow when migrating so that artifacts are built and attested only once.

Copy:

| Template                        | Destination                            |
| ------------------------------- | -------------------------------------- |
| `release_please.yml`            | `.github/workflows/release_please.yml` |
| `release_please_config.json`    | `release_please_config.json`           |
| `.release_please_manifest.json` | `.release_please_manifest.json`        |

Then configure the following:

1. Choose the release strategy in the config: `node` for npm, `rust` for Cargo, or `simple`
   for a project with `version.txt`. Create the strategy's version file if needed. Set the
   initial version and tag convention for the project. For an existing project, seed the
   manifest with its last released version; `0.0.0` is only for a project with no releases.
2. Keep `draft: true` and `force-tag-creation: true`. The tag is needed for checkout and
   recovery while the GitHub release remains a draft. Configure prereleases and version bumps
   for the project's compatibility policy rather than copying another project's version.
3. Set `RELEASE_PLEASE_TOKEN` for the destination repository with Contents, Issues, and Pull
   requests write access. A GitHub personal access token lets generated PRs trigger CI.
   Copying a workflow does not copy repository secrets.
4. Replace the deliberately failing build step with toolchain setup, locked dependency
   installation, tests, packaging, and smoke tests of the actual archives. Put only final
   distribution files and their checksums in `.release/`; ignore that directory in Git.
   Do not use caches for privileged release builds without a separate trust assessment.
5. If publishing to a package registry, insert publication of those same tested archives
   before the final GitHub publication step. Handle an already published version by comparing
   its digest, not by silently treating every conflict as success.
6. Enable immutable releases in the destination repository. Assets are attached to a draft
   before publication. The workflow permits replacing draft assets for recovery, and rejects
   attempts to modify a published release.

All release operations are serialized and do not cancel a running publication. A build failure
leaves a draft. Resume at the exact tag, for example:

```sh
gh workflow run release_please.yml --ref v0.1.0 -f tag_name=v0.1.0
```

The workflow checks that checkout matches the workflow's source commit and that manual runs
select the same tag. Selecting `main` while passing an old tag would give provenance the wrong
source commit. If the normal push run encounters a newer main commit than the release tag,
resume from that tag. Correct a published release with a new version rather than overwriting it.

## Template maintenance

GitHub Actions lint validates the workflow templates as well as deployed workflows. Zizmor
receives a temporary `.github/workflows/` tree containing the templates so its normal discovery
rules apply. Renovate's `github-actions.managerFilePatterns` includes `templates/*.yml` and
`templates/*.yaml`, preserving action SHA and version-comment updates.

Sources: [Release Please](https://github.com/googleapis/release-please-action),
[immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases),
and [Renovate file matching](https://docs.renovatebot.com/modules/manager/github-actions/).
