# ADR-0016: Own personal agent source in dotfiles

- Status: Accepted
- Date: 2026-08-28

In the context of managing one user's machines with Nix while also deploying the same Claude Code
and Codex behavior through agent-harness, facing a separate profile repository that would add a
third update and review boundary and a public harness repository that changed for personal policy
edits, we decided for owning the complete flat source under `agents/` in dotfiles, composing pinned
Herdr and Moshi outputs in Home Manager, and keeping the source-specific Bats and Python tests next
to that source, and against an author profile in agent-harness or another dedicated profile
repository, to make personal configuration changes atomic with the Nix configuration that deploys
them, accepting that non-Nix hosts need a separately produced deployment artifact rather than
cloning dotfiles as an installer.
