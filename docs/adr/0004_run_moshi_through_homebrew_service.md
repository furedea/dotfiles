# ADR-0004: Run Moshi through the Homebrew user service

- Status: Superseded
- Date: 2026-08-20
- Superseded by: ADR-0009

In the context of a MacBook Pro acting as the remote agent host while a MacBook Air acts as a
client, facing an upstream Moshi runtime that already publishes a Homebrew service and stores its
pairing credentials in the user Keychain, we decided for an MBP-scoped Homebrew user service with
non-fatal read-only status checks and against a shared service, a custom LaunchAgent, or Nix-managed
pairing secrets, to reuse the supported lifecycle while preserving the credential boundary,
accepting host-specific flake outputs and that Moshi starts only after the user logs in.
