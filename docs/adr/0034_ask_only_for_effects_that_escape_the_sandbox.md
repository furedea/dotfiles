# ADR-0034: Ask only for effects that escape the sandbox

- Status: Accepted
- Date: 2026-10-15
- Supersedes: ADR-0031

In the context of the three command tiers from
[ADR-0031](0031_permit_agent_commands_by_reversibility.md), facing an OS sandbox that now confines
every agent command to the worktree and temp directories, allowed network hosts, and unreadable
credential paths, and audit evidence that script execution, in-place edits, and read-only
inspection with globs, variables, or regex metacharacters were prompting dozens of times a day
without anyone inspecting them, we decided for allowing what the sandbox contains, namely script
execution with `python`, `node`, and `uv run python`, in-place edits such as `sed -i` and `tee`,
trivial builtins, and read-only programs with any argument as long as no redirection writes a
file, and for asking only about effects that escape the sandbox or cannot be undone, namely
fetched-package execution, dependency changes, deletions of untracked files, merges, publishing,
remote changes, and the sandbox escape itself, while denying what ADR-0031 denied, and against
keeping the classifier as the default judge of unlisted commands or widening the precise rules one
form at a time, to make ordinary work prompt-free and deterministic while the sandbox and the
hard denials carry the safety, accepting that a script may rewrite or delete untracked files inside
the worktree, that a run-time argument to a non-read-only program still prompts, and that the
prompt is only as strong as the sandbox configuration behind it.
