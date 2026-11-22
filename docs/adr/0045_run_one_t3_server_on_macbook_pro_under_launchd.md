---
status: accepted
date: 2026-11-22
related: [ADR-0018, ADR-0041]
---

# Run one T3 server on MacBook Pro under launchd

## Context and Problem Statement

T3 Code threads run Claude and Codex with the user's rights, and they should stay reachable from
MacBook Air and an iPhone over the existing Tailscale tailnet, without depending on a desktop window
staying open. By default each desktop app starts its own server on `~/.t3`, so threads stop when the
app quits and exist only on that machine. Two servers cannot share one `~/.t3`: the second takes an
exclusive lock on `server-owner.sqlite` and exits 78. Issue #489 tracks the work.

## Considered Options

- A launchd user agent on MacBook Pro runs `t3 serve` on loopback, Tailscale Serve publishes HTTPS
    8443, and every desktop app is a client (the desktop app's Local environment is off).
- Keep the desktop-owned server and reach it from other devices.
- T3 Connect, the vendor relay.
- `t3 up` / `t3 service install`, T3's own service installer.

## Decision Outcome

Chosen option: "A launchd user agent on MacBook Pro runs `t3 serve` on loopback, Tailscale Serve
publishes HTTPS 8443, and every desktop app is a client", because it keeps threads running when no
app is open, keeps state in the existing `~/.t3`, and reuses the shape of ADR-0018: one server on the
home machine, loopback bind, Tailscale Serve, a host flag in `flake.nix`. The agent runs the Nix
`t3` (whose Codex is the signed release of ADR-0041) with an explicit `HOME` and `PATH`; the server
uses port 3774 so it never meets the desktop's own 3773. `pmset -c sleep 0` keeps the machine awake
on the charger. Pairing and `tailscale serve` stay outside this repository.

The other options lose on one point each:

- The desktop-owned server stops when the app quits and is reachable only while that window is open.
- T3 Connect makes a vendor relay hold the signing authority for access to an agent runtime and
    needs a Clerk account.
- `t3 up` and `t3 service install` write an unmanaged plist and binaries under `~/.t3/runtime`,
    outside Nix, so the version, PATH, and Codex signing are no longer declared here.

### Consequences

- Good, because threads survive closing or restarting any desktop app, and one server owns all
    state.
- Good, because no credential enters the plist or the Nix store; devices authenticate by pairing.
- Bad, because the server is unavailable whenever MacBook Pro, the agent, or the Tailscale path is
    down, and MacBook Pro stays awake on the charger.
- Bad, because the desktop app on MacBook Pro must have Local environment off before the agent
    starts; while it is on, the agent exits 78 and `ThrottleInterval = 60` retries once a minute.
- Bad, because the server runs agents with the user's rights, so any paired device can drive them;
    pairings are revoked by hand.
- Bad, because pairing needs steps outside this repository: `t3 pair --tailscale` did not set up
    Tailscale Serve, so `tailscale serve --bg --https=8443 http://127.0.0.1:3774` is run by hand,
    and the tailnet ACL must allow `tcp:8443` to MacBook Pro. Pairing tokens are one-time and expire
    after 5 minutes, so `t3 pair` runs in the user's own terminal, its output is pasted nowhere, and
    the token is opened only in the client being paired (opening it in a browser first consumes it).
    The pairing URL and QR also go to `~/.t3/userdata/logs/launchd-server.log`. Turning Local
    environment off leaves a stale "T3 Code Desktop" authorized client to revoke.
- Bad, because the iOS app alerts only through push via the T3 relay, which needs a T3 account; none
    is used, so the iPhone gets no alerts. Desktop clients notify locally.
- Bad, because the iOS app is reported upstream to drop Tailscale connections within minutes
    (pingdotgg/t3code#25405, #24909); in the real-device check it did not occur, and the iPhone app
    stayed connected for several minutes.

Accepted after the real-device check in Issue #489: MacBook Pro, MacBook Air, and the iPhone app are
paired, a thread kept running and completed with the MacBook Pro desktop app quit, and approvals
answered from the MacBook Air desktop app and the iPhone app let the thread continue.
