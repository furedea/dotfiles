# ADR-0036: Review only commands that reach past the sandbox

- Status: Accepted
- Date: 2026-10-17
- Supersedes: ADR-0034

In the context of the sandbox tiers from
[ADR-0034](0034_ask_only_for_effects_that_escape_the_sandbox.md) and agent git running inside the
sandbox under [ADR-0035](0035_run_agent_git_inside_the_sandbox_with_unsigned_commits.md), facing a
replay of a day's agent commands in which 56 of 58 prompts came from local commands that merely
used a shell variable or a form the precise allowlist did not list, such as `git -C $W add`,
`git commit -S`, or `sed -i ''`, while only two were real denials, we decided for letting every
command whose effects stay on the machine take any form unless a forbidden rule or the
dangerous-Git guard denies it, for keeping precise forms only for programs that reach past the
sandbox (`gh`, `curl`, and `wget`), judging a run-time word there as a plain placeholder so that
it passes only where any value would, and for asking about a run-time Git word only when it can
hide a denial (the program or subcommand, an argument of a verb judged by its options, or the
repository whose current branch an implicit push updates), and against widening the local
allowlist form by form or keeping run-time words a prompt everywhere, to reserve prompts for
effects the sandbox cannot undo, accepting that the hard denials see only literal words, so a
variable that expands to a forbidden flag of a local command such as `--no-verify` is not caught,
and that the prefixes the provider itself asks about, such as `rm`, dependency changes, and
merges, still prompt.
