---
status: proposed
date: 2026-11-26
related: [ADR-0045, ADR-0051]
---

# ADR-0053: Sync atuin through a self-hosted server on MacBook Pro

## Context and Problem Statement

Atuin threads capture the sessions of coding agents (conversation, tool input and output, token
usage) so harness improvements can be analyzed from one record per session. Capture writes into the
same encrypted record store that shell history sync uses. Keeping `sync.records = true` against
Atuin's cloud would send every agent conversation, even encrypted, to a third party; turning sync
off would also stop shell history sync and keep each Mac's threads on that Mac only.

Atuin's server is open source. Its record API stores any record tag, and upstream's own end-to-end
tests sync `ai-session` records between two machines through an in-process server of the same code
(`crates/atuin/tests/e2e_ai_sessions.rs`, `common/ai.rs`), so threads sync through a self-hosted
server the same way history does.

## Considered Options

- Keep syncing through Atuin's cloud.
- Turn sync off.
- Self-host the server on MacBook Pro and reach it from MacBook Air over the tailnet.

## Decision Outcome

Chosen option: "Self-host the server on MacBook Pro", because it keeps both shell history sync and
the threads on the two Macs while the data stays on hardware the owner controls. It follows the
pattern of the former Hister server (ADR-0018) and the T3 server (ADR-0045).

- A host flag (`enableAtuinServer`, true for `mbp` only) adds a launchd agent running
    `atuin-server start` with SQLite under `~/.local/state/atuin-server`, bound to `127.0.0.1:8888`,
    with `ATUIN_OPEN_REGISTRATION=false`. Settings are environment variables in the plist, so no
    file needs editing; `ATUIN_CONFIG_DIR` points the server's example `server.toml` into its
    state directory instead of the Nix-managed `~/.config/atuin`.
- The nixpkgs `atuin` builds only the client, so `nix/packages/atuin_server.nix` builds the
    `atuin-server` package of the same source and vendored dependencies; the server cannot drift from
    the client version.
- Tailscale Serve publishes it on HTTPS 8444 (T3 keeps 8443). Both Macs set `sync_address` to
    `https://mbp.tailbb556b.ts.net:8444`; `evaluation` contracts fail if either points at `atuin.sh`.
- `[threads] capture = true` on both Macs. The daemon that captures runs as a Nix-managed launchd
    agent (`programs.atuin.daemon.enable`) and `daemon.autostart` stays false, because autostart
    lets atuin install and rewrite its own launchd agent outside Nix.

### Consequences

- Good, because conversations and tool output never reach Atuin's service, and shell history sync
    keeps working.
- Good, because registration is closed by default and the server is reachable only over the tailnet.
- Bad, because sync is unavailable while MacBook Pro, the agent, or the Tailscale path is offline;
    the Mac keeps recording locally and catches up later.
- Bad, because every thread is replicated to MacBook Air, which needs the disk space.
- Bad, because the account, `tailscale serve`, and the one-time registration stay manual, and the
    tailnet ACL must allow `tcp:8444` to MacBook Pro.
- Bad, because the server and the client share a version only through the same nixpkgs source; a
    nixpkgs change that splits them would need this package to follow.
