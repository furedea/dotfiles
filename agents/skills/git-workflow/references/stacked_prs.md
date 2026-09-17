# Stacked Pull Requests

Use this reference only when the user explicitly asks for a stacked pull request or a red-green
bug fix. Do not decide on your own that a bug deserves a stack; an ordinary fix request keeps the
test and the implementation in one commit and one pull request.

## Red-Green Bug Fix

A red-green stack records the Red observation from `tsdd` as CI evidence that outlives review.

| Layer | Branch           | Contents                                                  | Green CI means                     |
| ----- | ---------------- | --------------------------------------------------------- | ---------------------------------- |
| 1     | `test/<subject>` | The reproduction test only, marked as an expected failure | The test fails on the current code |
| 2     | `fix/<subject>`  | The fix and the removal of the expected-failure marker    | The same test passes with the fix  |

Expected-failure markers: pytest `@pytest.mark.xfail(strict=True, reason=...)`, Vitest
`test.fails`, Jest `test.failing`, Playwright `test.fail()`. The marker and its comment follow the
relevant `*-style` skill. Rust and Bats have no strict marker; do not use a stack for them.

Green on layer 1 proves only that the test fails, not why. Confirm the failure reason locally
before publishing, as `tsdd` requires for Red.

## Workflow

1. Start on an up-to-date default branch with a clean working tree, then run `git fetch origin`.
2. `gh stack init test/<subject>` creates layer 1 from the default branch and checks it out.
3. Add the reproduction test with its marker and comment. Commit as
   `test(<scope>): <subject written from the specification's perspective>`.
4. `gh stack add fix/<subject>` creates layer 2 on top of layer 1 and checks it out.
5. Remove the marker and its comment, implement the fix, and commit as `fix(<scope>): ...`.
6. `gh stack submit --auto` pushes both branches and opens two linked draft pull requests. Set
   each title and body with `gh pr edit`, then mark them ready with `gh pr ready`.
7. Report the stack with `gh stack view --short`.

Rules:

- Both layers share the same kebab-case `<subject>`.
- `gh stack init` without a branch name and `gh stack submit` without `--auto` are interactive;
  do not use them.
- Push follow-up commits to a layer with `git push origin <branch>`. When a lower layer changes,
  `gh stack rebase` rebases the layers above it and `gh stack push` publishes them with the same
  lease policy as [Delivery](delivery.md); stop and ask the user if a lease is rejected.
- Merging is a human decision. `gh stack merge` and the GitHub "Merge stack" button merge the
  whole stack all-or-nothing; when the user asks for it, the approval prompt is the authorization.
