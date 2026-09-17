# ADR-0032: Bound external agent audit logs

- Status: Accepted
- Date: 2026-09-18

In the context of native Claude Code and Codex hook observations, facing repository-local logs
that could retain prompts, commands, patches, URLs, and unbounded history, we decided for
provider- and worktree-scoped metadata-only JSONL logs in the user's state directory with
retention, per-file, and total-size limits, and against copying event bodies into audit records or
letting observability failures affect enforcement, to keep audit data useful without making the
repository a transcript store, accepting that existing repository logs require an explicit manual
migration decision if they ever need to be retained elsewhere.
