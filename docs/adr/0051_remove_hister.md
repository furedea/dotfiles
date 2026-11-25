---
status: proposed
date: 2026-11-25
supersedes: [ADR-0018]
---

# Remove Hister

## Context and Problem Statement

ADR-0018 runs one Hister server on the MacBook Pro, publishes it over Tailscale Serve, and installs
the client on both Macs. Upstream renamed the project to Nogon, so keeping it needs a change anyway.
Review of actual use found that its search was never used on purpose (the recorded queries were
web searches the extension logged), that its browser extension can read every site and cookies,
that the server exposes every visited page to the tailnet, and that its AI (MCP) interface is not
wired to any agent.

## Considered Options

- Keep it and follow the rename to Nogon.
- Remove it completely.

## Decision Outcome

Chosen option: "Remove it completely", because nothing uses it and its reach (all sites, all
visited pages on the tailnet) is far larger than the value it gives.

### Consequences

- Good, because no extension reads every site, and no service holds the browsing history or listens
    for it.
- Good, because the flake input, package, launchd agent, launcher, client config and tests leave the
    repository; the `evaluation.host-configuration` contracts fail if a host installs it again.
- Bad, because searching the shared browsing history is no longer available.
- Cleaning a host is manual: remove the browser extension and its site-search keyword, the
    Tailscale Serve route, the data directory, the Keychain item, and the client config directory.
