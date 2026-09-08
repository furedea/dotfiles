# Source Acquisition

Read only the section matching the requested target. Use read-only operations and preserve the
target's exact identity. Do not post comments, change labels, check out a branch, or modify source
material as part of explanation.

## Local Document or Implementation Brief

Read the complete file, including appendices and footnotes. Follow a referenced local file when it
is declared authoritative, supplies a prerequisite, or resolves an apparent contradiction. Do not
recursively read every incidental link.

Record:

- The repository-relative or absolute path.
- The current Git commit when the file is tracked.
- Whether the represented content contains working-tree changes.
- `untracked` or `unversioned` when no commit identifies the content.

When the working tree differs from the commit, record both `HEAD <sha>` and `working-tree changes`;
do not imply that the committed version was reviewed.

## Pull Request

Resolve both the repository and pull request number. With an authenticated GitHub CLI, useful
read-only acquisition commands include:

```text
gh pr view <number> --repo <owner/repo> \
  --json title,body,url,state,headRefOid,baseRefOid,additions,deletions,changedFiles,commits,reviews
gh pr view <number> --repo <owner/repo> --comments
gh pr diff <number> --repo <owner/repo> --name-only
gh pr diff <number> --repo <owner/repo>
```

Read the description, relevant discussion, complete diff, and the changed source files that define
the central data structures, execution path, or external boundaries. Obtain file content from the
PR head revision rather than silently reading a different local branch. Record `headRefOid` as the
represented revision and `baseRefOid` as comparison context.

Follow linked issues, pull requests, or external documents only when they control acceptance,
scope, rationale, dependency readiness, or another material part of the explanation. List material
links that could not be read.

## Issue

Read the issue body and all accessible comments. With an authenticated GitHub CLI, a useful
read-only command is:

```text
gh issue view <number> --repo <owner/repo> \
  --comments --json number,title,body,url,state,updatedAt,comments
```

Prioritize acceptance conditions, explicit non-goals, dependencies, and later corrections to
earlier statements. Do not assume that the newest statement is authoritative when participants or
controlling sources disagree; expose the conflict.

An issue has no commit SHA. Record the issue URL, its `updatedAt` value, the latest relevant comment
timestamp, and the retrieval time as the represented snapshot.

## Remote Document

Use an available read-only browser, connector, or retrieval tool. Record the canonical URL and the
strongest revision identifier exposed by the source, such as a version, commit, document revision,
or last-updated timestamp. If only a retrieval time is available, say so explicitly.

If access is incomplete, distinguish inaccessible content from content intentionally excluded as
immaterial. Never fill an access gap with an inferred claim.
