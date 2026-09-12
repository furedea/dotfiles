# ADR-0025: Pin Moshi in Nix

- Status: Accepted
- Date: 2026-09-12
- Supersedes: ADR-0003, ADR-0005, ADR-0009

In the context of generating agent hooks and running the Keychain-backed Moshi host on macOS,
facing different generator and runtime versions plus automatic Homebrew upgrades, we decided for a
single pinned Nix package used by hook generation, the user command, and a Home Manager-owned Aqua
LaunchAgent, and against the Homebrew formula and its update watcher, to keep the hook contract and
runtime reproducible from one configuration, accepting manual version and hash updates and that the
host remains unavailable before GUI login unlocks the Keychain.
