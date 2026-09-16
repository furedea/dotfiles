# ADR-0029: Register verification in native hooks

- Status: Accepted
- Date: 2026-09-16
- Supersedes: ADR-0028

In the context of automatic verification for Claude Code and Codex, facing the
maintenance cost and CLI restrictions of a custom launcher, we decided for
synchronous native SessionStart registration, PreToolUse registration checks,
and Stop verification, and against intercepting provider startup or relying on
model-invoked registration, to capture the baseline before agent tools execute
using each provider's own lifecycle, accepting the providers' hook delivery and
failure semantics rather than claiming a filesystem enforcement boundary.

Provider session IDs let repeated starts and resumes retain the original baseline
and evidence without a launcher environment variable. When no record exists for a
resumed, cleared, or forked session, full revalidation avoids guessing its predecessor
or silently accepting previous work. Inactivity-based retention bounds abandoned
records without a parent process lease.

Both [Codex](https://developers.openai.com/codex/hooks/) and
[Claude Code](https://code.claude.com/docs/en/hooks) support synchronous command
hooks. A missing or invalid registration is explicitly denied at PreToolUse;
disabled hooks, hook startup failures, and provider-level timeouts remain subject
to native behavior. The scripts do not infer task completion from model prose.
