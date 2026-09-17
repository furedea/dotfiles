# Commits

Commit by intent, not by file.

- One user-visible feature, bug fix, refactor, documentation update, or config change per commit.
- Tests for a new behavior belong in the same commit as the implementation. A stacked red-green bug fix requested by the user is the exception: its reproduction test is its own commit on its own layer. See [Stacked pull requests](stacked_prs.md).
- Test-only coverage for existing behavior uses `test:`.
- Generated files and lockfiles belong with the change that caused them.
- Pure formatting belongs in `style:` when it would obscure a logic review.
- Do not fabricate splits. One cohesive change should be one commit.

Before an authorized commit, follow [Local Verification Before Delivery](delivery.md#local-verification-before-delivery).

## Conventional Commits

Use Conventional Commits for every commit message.

```text
<type>(<scope>): <imperative subject>
```

Scope is optional:

- Use scope when all changed files clearly live in one module or area.
- Omit scope when the commit spans multiple top-level areas or repo-root files.
- Keep scope lowercase, single-word, and without slashes.

Subject rules:

- Imperative mood: `add`, `fix`, `remove`, `rename`.
- Lowercase first letter unless it is a proper noun or identifier.
- No trailing period.
- Aim for 50 characters or fewer; hard cap at 72.
- Describe behavior or intent, not filenames.

Use a body only when the why is not obvious from the subject. Wrap body text at about 72 columns.

Common types:

| type       | when to use                                      |
| ---------- | ------------------------------------------------ |
| `feat`     | new user-visible capability                      |
| `fix`      | bug fix                                          |
| `refactor` | restructure without behavior change              |
| `perf`     | performance-only change                          |
| `docs`     | documentation only                               |
| `test`     | test-only change for existing behavior           |
| `build`    | build system, packaging, dependencies, lockfiles |
| `ci`       | CI configuration only                            |
| `chore`    | tooling/config that does not fit elsewhere       |
| `style`    | formatting only, no logic change                 |
| `revert`   | reverts a previous commit                        |

Examples:

```text
feat(auth): add JWT refresh-token rotation
fix(parser): handle empty input without panicking
refactor(db): extract query builder from repository
docs: clarify install steps for Apple Silicon
test(auth): cover refresh-token expiry edge case
build(deps): bump axios from 1.6.0 to 1.7.2
```

For explicit commit requests:

1. Inspect staged, unstaged, and untracked changes, then group them using the intent rules above. Do not assume the existing staging matches the intended commit boundaries.
2. When unrelated intents share a file, stage only the relevant hunks. Do not rewrite the working file to manufacture a split.
3. Before each commit, inspect `git diff --cached` and confirm it contains only the intended change, including any changes made by hooks. Commit with a Conventional Commits message.
4. Before preparing the next commit, regenerate the diff against the current index and HEAD. Do not reuse patches or hunk numbers from before the previous commit.
