# ADR-0019: Use Apple Mail as the secretary mail boundary

- Status: Accepted
- Date: 2026-08-30
- Supersedes: ADR-0014

In the context of a macOS Hermes secretary that must cover multiple mail
providers already configured in Apple Mail, facing separate provider OAuth
state and account configuration in Himalaya, we decided for the revision-pinned
`apple-mail-cli` upstream flake and against Himalaya, direct provider APIs, and
Mail database access, to reuse the operating system's existing accounts while
preserving bounded JSON reads and preview-before-execute mutations, accepting a
dependency on Apple Mail, Apple Events, and macOS Automation permission.
