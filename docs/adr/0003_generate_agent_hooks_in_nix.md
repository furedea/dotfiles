# ADR-0003: Generate agent hooks in Nix

- Status: Accepted
- Date: 2026-08-20

In the context of Home Manager owning Claude and Codex configuration while Herdr and Moshi own
their hook protocols, facing direct installers that conflict with immutable Home Manager symlinks
and hook output that changes with tool releases, we decided for running pinned installers in an
isolated Nix build and passing versioned bundles through agent-harness, with a pinned Nix Moshi
binary for generation and Homebrew Moshi for runtime, and against activation-time installers or
vendored hook JSON, to preserve upstream output without exposing mutable pairing state to Nix,
accepting that the pinned generator must be reviewed when the Homebrew runtime changes its hook
contract.
