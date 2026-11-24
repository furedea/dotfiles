---
status: proposed
date: 2026-11-25
supersedes: [ADR-0025]
---

# Remove Moshi

## Context and Problem Statement

ADR-0025 pins the Moshi hook binary in Nix, runs it as a launchd daemon on the MacBook Pro, and
composes its generated hooks into every agent. A review of moshi-hook 0.4.62 (static reading of its
strings and bundled documentation) found that the closed-source daemon reads the local state of
several agents about once a minute to call their usage APIs, keeps a persistent WebSocket
connection to the Moshi cloud relay that carries sessions, prompts and approval commands, and
updates itself every six hours. Those behaviors are broader than a hook bridge needs, and the
binary cannot be audited at the source level.

## Considered Options

- Keep Moshi with its usage collection, relay, and auto-update turned off.
- Remove Moshi completely.

## Decision Outcome

Chosen option: "Remove Moshi completely", because the hook bridge needs the cloud relay to be
useful at all, so turning the relay off leaves nothing worth running, and the binary is closed, so
the remaining switches cannot be verified.

### Consequences

- Good, because no closed-source daemon reads agent state, holds a relay connection, or updates
    itself outside Nix.
- Good, because the package, its launchd agent, lifecycle script, update workflow and hook bundle
    leave the repository; the `evaluation.host-configuration` contracts fail if any host installs
    moshi-hook again.
- Bad, because approving and observing agent sessions from the iPhone app is no longer available.
- Cleaning a host is manual: run `moshi-hook uninstall` and remove `~/.config/moshi` and the
    paired key in `authorized_keys`.
