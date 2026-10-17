# ADR-0035: Run agent git inside the sandbox with unsigned commits

- Status: Accepted
- Date: 2026-10-17

In the context of Claude Code agents that commit and push through the sandbox described in
[ADR-0034](0034_ask_only_for_effects_that_escape_the_sandbox.md), facing commit signing that cannot
reach the SSH agent inside the sandbox and therefore kept `git commit` and its neighbors excluded,
so that repository git hooks also ran outside the sandbox and an agent could run code there by
editing `lefthook.yml`, a script a hook calls, or build settings that a hook's tool reads, we
decided for leaving agent commits and tags unsigned through the Claude environment, running agent
git and its hooks inside the sandbox, and authenticating pushes with the agent GitHub App token,
and against keeping git outside the sandbox while disabling or guarding hooks, wrapping hooks in a
separate sandbox runtime, or signing inside the sandbox through the SSH agent socket, to keep the
hooks' quality checks automatic while no repository-controlled code runs outside the sandbox,
accepting that agent branch commits carry no user signature, that main stays signed only because
agent changes reach it through squash merges that GitHub signs, which the dangerous-Git guard
enforces by refusing pushes to main, and that the user's own commits keep signing and hooks.
