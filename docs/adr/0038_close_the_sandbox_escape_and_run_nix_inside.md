# ADR-0038: Close the sandbox escape and run Nix inside

- Status: Accepted
- Date: 2026-10-17

In the context of [ADR-0036](0036_review_only_commands_that_reach_past_the_sandbox.md), which
reserves prompts for effects the sandbox cannot contain, facing sessions that read an empty
`gh` output or another ordinary failure as a sandbox denial and retried the command with the
sandbox disabled, a retry that the `Bash(dangerouslyDisableSandbox:true)` ask rule turns into a
prompt that no hook can answer, and Nix commands that needed the escape only because the daemon
socket was unreachable, we decided for closing the escape with `allowUnsandboxedCommands: false`,
for reaching the Nix daemon socket from inside the sandbox, and for keeping Herdr, Docker, and
Watchman as the only excluded tools, and against denying escapes per command in a hook, telling
agents in instructions not to escape, or moving `gh` back outside the sandbox, to remove the
source of those prompts rather than answer them one by one, accepting that a command the sandbox
cannot run now fails and is reported for the user to run with `!`, that builds the Nix daemon
performs reach the network outside the sandbox proxy as they did before, and that the ask rule
stays only as a second layer should a runtime ignore the setting.
