---
status: accepted
date: 2026-11-25
related: [ADR-0045, ADR-0047]
---

# Keep T3 Code from sending telemetry

## Context and Problem Statement

T3 Code sends product usage events to a PostHog-compatible endpoint (`ingest.t3.codes`) and relay
connection traces to Axiom (`api.axiom.co`) by default. The documented opt-outs are an environment
variable (`T3CODE_TELEMETRY_ENABLED`, off only when it parses as false) and a managed policy file
(`limits.telemetry: false`). The opt-out was not honored for a period in the desktop app and in relay
traces (fixed upstream in pingdotgg/t3code#16563 and #14413), and the app updates often, so one
switch is not enough evidence that nothing is sent. T3 runs on MacBook Pro (launchd `t3-server`,
desktop app, manual `t3`) and MacBook Air (desktop app, manual `t3`). Issue #506 tracks the work.

## Considered Options

- Four layers: the environment variable, the managed policy, hosts-file blocking, and a check on
    each T3 update, with Nix contracts for the declarative parts.
- The environment variable only.
- An outbound firewall such as LuLu.

## Decision Outcome

Chosen option: "Four layers", because each layer fails differently and the others still hold: a
regression in how T3 reads the variable does not matter while the policy and the blocked hosts hold,
and the check notices a new endpoint or a lost layer instead of waiting for a leak.

- Config: `T3CODE_TELEMETRY_ENABLED=false` in `zsh/.zshenv` (the desktop app starts `$SHELL -ilc` and
    forwards it to its bundled server), in the `t3-server` agent's environment, and in the launchd
    user environment through a one-shot agent (`launchctl setenv`) for apps started from the Dock.
    `T3CODE_OTEL_SDK_DISABLED=true` goes to the same three places as belt and braces: relay tracing
    runs only when telemetry is not false and OTel export is not disabled, so either variable stops it.
    It does not stop product events and would also stop user-configured OTLP export (none is
    configured). The desktop app forwards only `T3CODE_TELEMETRY_ENABLED` from the login shell, so
    for it the launchd environment carries this one. The generic `OTEL_SDK_DISABLED` is not set; it
    would affect other tools.
- Policy: darwin activation writes `/Library/Application Support/T3Code/policy.json` with
    `limits.telemetry: false`, root-owned, so no user setting or app regression can turn it on. Only
    the file is used: a native configuration profile together with the file makes T3 refuse to start.
- Network: darwin activation rewrites a marked block of `/etc/hosts` that maps `ingest.t3.codes`,
    `api.axiom.co`, and `relay.t3.codes` to `0.0.0.0` and `::`. nix-darwin has no `networking.hosts`
    option. The rewrite never touches lines outside the block and leaves the file unchanged when the
    markers are duplicated or unpaired. `relay.t3.codes` is blocked because T3 Connect is unused
    (ADR-0045).
    The rewriter names its block with `HOSTS_BLOCK_NAME` (default `t3-telemetry-block`, so the block
    already on a machine is rewritten in place); other tools' telemetry hosts use their own block
    (`app-telemetry-block`), and no block touches another.
- Check: home-manager activation runs `scripts/t3/check_telemetry.sh` when the T3 server bundle's
    store path changed since the last check. It checks the policy, the hosts, the launchd environment
    and the server agent, and diffs the `https://` hosts and `T3CODE_*` / `OTEL*` names found in the
    bundled JS against the last scan, then records the result under `~/.local/state/t3-telemetry`.
    Problems are warnings and never fail a switch.
- Contracts: `nix/checks.nix` asserts the declarative layers at build time.

Hosts left unblocked on purpose: `app.t3.codes`, GitHub, npm, and `u.expo.dev` carry the hosted app,
release downloads, and security updates, and blocking them would stop those updates. The Clerk
telemetry host (`clerk-telemetry.com`) appears in the bundle; Clerk is unused here, so it is left to
the check's diff rather than blocked.

### Consequences

- Good, because a single upstream regression no longer sends data silently, and a new endpoint or a
    dropped layer surfaces as a warning at the next switch.
- Bad, because hosts-file blocking is name-based: a hard-coded IP, DNS over HTTPS, or a new host name
    bypasses it, and the check only reports new names after the fact.
- Bad, because after a clean check the next one waits for a new T3 store path; a layer that breaks
    between updates is noticed at the next update or when the check is run by hand. A check with
    warnings is not recorded, so it reruns on every switch until it passes.
- Bad, because the check reads the unwrapped server bundle only; the desktop app's own bundle is not
    scanned.
- Bad, because the phone (crash-report toggle, NextDNS), an outbound firewall, and reporting upstream
    stay outside this repository.
