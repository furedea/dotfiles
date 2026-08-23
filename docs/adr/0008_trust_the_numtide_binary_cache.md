# ADR-0008: Trust the Numtide binary cache

- Status: Accepted
- Date: 2026-08-23

In the context of installing `llm-agents.nix` packages on two Macs, facing lengthy local Codex
builds and the security impact of an additional binary distributor, we decided for pinning
Numtide's cache URL and current public key in the shared nix-darwin configuration and against
local-only builds, arbitrary flake configuration acceptance, or broader trusted-user privileges,
to obtain signed substitutes with an auditable trust boundary, accepting that Numtide's signing
infrastructure can provide any requested store object it signs rather than only the selected agent
packages.
