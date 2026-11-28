---
status: proposed
date: 2026-11-28
related: [ADR-0045, ADR-0046, ADR-0048]
---

# Add the Herdr app next to T3 Code

## Context and Problem Statement

T3 Code (ADR-0045 to ADR-0048) is the desktop client for agent sessions, and its telemetry needs four
layers of upkeep. The owner distrusts it but keeps it until the Herdr desktop app (`herdr-app`,
Apache-2.0, bundling `herdr-core`) proves sufficient. The Herdr terminal UI is already managed here.
The app sends an anonymous usage report each day by default. It stops only when
`~/.config/herdr-app/settings.json` has `"telemetry": false`; the `DO_NOT_TRACK` and `HERDR_TELEMETRY`
variables do not reach an app started from the Dock.

## Considered Options

- Replace T3 Code with the Herdr app now.
- Install the Herdr app next to T3 Code, with its telemetry off, and remove T3 Code later.

## Decision Outcome

Chosen option: "Install the Herdr app next to T3 Code", because the replacement is not yet proven, and
the telemetry switch must be declared from the first launch.

- The `herdr-app` Homebrew cask is installed on both Macs; the Herdr terminal UI stays as it is.
- Activation merges `"telemetry": false` into the app's settings file, as ADR-0046 does for T3
    settings, because the app writes that file itself and a read-only link would break it.
- `telemetry.herdr.dev` joins the hosts block that holds other apps' telemetry hosts, as a second layer.

### Consequences

- Good, because the app never reports usage, even on its first launch.
- Bad, because a change in the settings key upstream would silently re-enable the report; the hosts
    block still stops it.
- Removing T3 Code later needs its own decision and supersedes ADR-0045 to ADR-0048.
