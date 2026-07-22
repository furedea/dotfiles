# ADR-0002: Manage Herdr plugins through Home Manager activation

- Status: Accepted
- Date: 2026-07-22

In the context of commit-pinned Herdr plugins that use a mutable registry and do not provide Nix packages, facing the need for reproducible installation without breaking Herdr's supported lifecycle, we decided for Home Manager activation through the official Herdr CLI and against immutable registry symlinks or custom per-plugin derivations, to reconcile the desired plugin set while preserving manual plugins, accepting that plugin artifacts remain outside the Nix store and updates require network access.
