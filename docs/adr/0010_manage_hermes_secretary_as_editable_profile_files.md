# ADR-0010: Manage Hermes secretary as editable profile files

- Status: Accepted
- Date: 2026-08-24

In the context of a Hermes secretary that learns and maintains its own identity,
skills, and routines while credentials and personal history must remain local,
facing Nix store links that would restore immutable source content on every
rebuild, we decided for Home Manager out-of-store links to the public SOUL,
secretary skill namespace, and cron directory, with cron runtime artifacts
ignored by Git and all authentication, provider configuration, memory, sessions,
and delivery state kept in the local profile, and against Nix store copies,
whole-profile version control, or unattended profile-distribution updates,
accepting that intentional Hermes edits appear as a dirty dotfiles working tree
and must be reviewed before commit.
