---
status: proposed
date: 2026-11-25
related: [ADR-0002]
---

# Link the Herdr reviewr plugin built from its pinned source

## Context and Problem Statement

ADR-0002 reconciles commit-pinned Herdr plugins with `herdr plugin install --ref`. The
`persiyanov.reviewr` manifest then runs `herdr/install.sh`, which downloads a prebuilt binary from
the matching GitHub release and checks it only against a checksum published beside it. The binary
that runs is therefore not built from the pinned commit, and the pin does not bound what executes.
Herdr's `plugin link` registers a local directory without running any build step, and the plugin
pane and actions only need `bin/herdr-reviewr` under the plugin root.

## Considered Options

- A Nix package (`nix/packages/herdr_reviewr_plugin.nix`) that builds the binary from the pinned
    commit with `buildRustPackage`, assembles a plugin directory without the `[[build]]` table, and
    has `plugin_sync.py` link it.
- Keep `plugin install` and accept the unverified release binary.
- Drop the plugin.

## Decision Outcome

Chosen option: "A Nix package that `plugin_sync.py` links", because the source hash and the cargo
lock hash then bound the code that runs, and the rest of ADR-0002 (reconciliation through the
official CLI, unmanaged plugins preserved) is unchanged. A declared plugin whose source is an
absolute path is linked; any other source is still installed from GitHub at its revision.

### Consequences

- Good, because a bumped revision changes the Nix hashes, and a build from other code fails.
- Good, because the activation no longer downloads anything for this plugin.
- Bad, because a revision bump now also needs a new `hash` and `cargoHash`, and the plugin is
    compiled on the machine (or fetched from a binary cache) instead of downloaded.
- Bad, because the plugin manifest is rewritten at build time (its `[[build]]` table removed) and
    can drift from upstream's layout; the `herdr-reviewr-plugin-layout` check fails when the binary,
    `herdr/pane.sh`, or the pane entry point disappears or a build step reappears.
