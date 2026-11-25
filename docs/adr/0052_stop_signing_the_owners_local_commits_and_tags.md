---
status: proposed
date: 2026-11-25
related: [ADR-0035, agent-config/ADR-0008]
---

# ADR-0052: Stop signing the owner's local commits and tags

## Context and Problem Statement

Home Manager configured Git to sign every local commit and tag with the 1Password SSH key through
a wrapper script. Every repository allows squash merge only, so the commits on main are created
and signed by GitHub; the local signature never reaches main. No main ruleset requires signatures,
and the latest release tags are lightweight tags that a release workflow creates unsigned. On the
MacBook Pro each signature needs a 1Password approval, which needs Screen Sharing when working
remotely.

agent-config ADR-0008 (kept reachable here as the stub ADR-0035) left agent commits unsigned and
stated that the user's own commits keep signing.

## Considered Options

- Keep signing every local commit and tag.
- Stop signing local commits and tags.

## Decision Outcome

Chosen option: "Stop signing local commits and tags", because the signature has no consumer
(GitHub re-signs what reaches main) and costs an approval on every commit.

This replaces the clause of agent-config ADR-0008 that says the user's own commits keep signing;
the rest of ADR-0008 (agent git inside the sandbox, unsigned agent commits) is unchanged.

### Consequences

- Good, because `git commit` in the owner's shell no longer prompts 1Password.
- Good, because the signing wrapper, its Bats spec, and the `gpg.*`/`user.signingkey` settings
    leave the repository; `evaluation.home-configuration` fails if signing returns.
- Bad, because direct commits to main that skip a pull request (the Obsidian vault backup) become
    unsigned. This was accepted explicitly.
- `~/.ssh/id_ed25519.pub` and its activation message stay, since SSH connections may use the key;
    the 1Password SSH agent itself is unchanged.
