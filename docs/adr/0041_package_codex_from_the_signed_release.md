# ADR-0041: Package Codex from the signed release

- Status: Accepted
- Date: 2026-11-02

In the context of Codex keeping its token in the macOS Keychain (`cli_auth_credentials_store =
"keyring"`), facing the `llm-agents` and nixpkgs builds being ad-hoc signed so that the Keychain
ACL stops matching after every update and Codex blocks waiting for approval, we decided for the
unmodified, Developer ID signed `codex-package` release of `openai/codex` pinned in Nix with an
install check that keeps the OpenAI team identifier, and against the `llm-agents` Codex package, to
let one "Always Allow" survive updates because a signed binary is matched by its designated
requirement, accepting that Codex is no longer updated through `nix flake update` but through the
`update-codex` workflow, and that the full package (including bundled voice resources) is installed.
