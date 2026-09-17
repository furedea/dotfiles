# ADR-0031: Permit agent commands by reversibility

- Status: Accepted
- Date: 2026-09-17

In the context of the command policy that Claude Code and Codex enforce through the shared hooks
from [ADR-0026](0026_use_python_for_automation_logic.md), facing a deny list that grew from a
Codex-era blocklist, left most commands to a non-deterministic classifier, and was bypassed by
process wrappers, install paths, and Git global options, we decided for three tiers chosen by
reversibility and blast radius, evaluated on the canonical command that a wrapper eventually runs,
and against keeping force pushes, worktree removal, and tracked-file deletion blocked outright or
leaving the classifier to judge them, to let agents finish ordinary Git and verification work
without prompts while reserving prompts for merges, dependency changes, and uninspectable scripts
and hard denials for credential access, global installation, system state, and unrecoverable
deletion, accepting that `--force-with-lease --force-if-includes` may rewrite the agent's own
published branches and that quality still rests on the verification hooks and CI rather than on
the permission layer.

Allow covers operations that reflog or HEAD can undo, read-only inspection, verification, builds,
and formatting; the precise regex rules additionally refuse redirections that would write files.
Ask covers merges, dependency and lock changes, package execution, writes that bypass the Edit
hooks, process signals, and Herdr pane control. Claude Code evaluates ask before allow, so an ask
prefix never sits above an allow prefix. Deny covers Keychain and gh credential commands, global
installs that Nix owns, macOS service and power state, recursive `rm`, and Git history rewrites.
Justifications stay provider-neutral because one file renders the Claude permissions, the Codex
execpolicy, and the hook allowlist.
