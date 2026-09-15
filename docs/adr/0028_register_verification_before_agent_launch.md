# ADR-0028: Register verification before agent launch

- Status: Accepted
- Date: 2026-09-15

In the context of automatic verification for terminal coding agents, facing
branch-wide Stop checks that include preexisting edits and cannot reliably infer
the worktree used by an arbitrary shell command, we decided for a launcher-owned
worktree baseline and native lifecycle hooks, and against model-invoked task
registration, completion tools, intent classification, or branch history as the
automatic verification boundary, to make verification independent of prompt
compliance while avoiding repeated tests on unchanged inputs, accepting a
controlled local CLI entry point and content hashing at verification boundaries.

The launcher persists the baseline before starting the provider. SessionStart
binds the provider session, and PreToolUse checks registration and observable
worktree paths. Stop verifies actual changes since launch using project test
mappings. A successful receipt is reusable only for identical inputs. An unchanged
failure remains unresolved without repeatedly blocking Stop; edits or an explicit
retry permit another attempt. This is an execution policy, not a semantic claim
that an implementation satisfies its requirements.

Private state belongs outside the repository. Atomic replacement, process leases,
bounded logs, and retention replace an accumulating per-turn history. Resume
retains available evidence and requires revalidation when its record has expired.
Native permissions remain responsible for filesystem isolation: lifecycle hooks
cannot observe every path used inside arbitrary code. App servers, remote sessions,
and provider-created worktrees need a registration boundary of their own before
they can use this policy.

See [the operating guide](../agent_verification.md) for entry points and storage,
and the executable contracts in `tests/agents/hooks/test_session_*.py`,
`test_launch_agent.py`, and `test_verification_session.py` for observable behavior.
