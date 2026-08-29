# ADR-0018: Centralize Hister on MacBook Pro

- Status: Accepted
- Date: 2026-08-29

In the context of sharing searchable browser history between MacBook Air and MacBook Pro over an
existing Tailscale tailnet, facing duplicated local indexes, intermittent mobile connectivity, and
an access token that must not enter the Nix store, we decided for running one Hister server on
MacBook Pro, binding it to loopback, publishing it through Tailscale Serve, and loading its access
token at runtime from the macOS login Keychain, and against independent per-host servers, direct
network exposure, a hosted Hister server, storing the token with SOPS, or adding a user-facing
credential helper, to unify history while keeping its index and credential on the home machine,
accepting that indexing is unavailable while MacBook Pro, Hister, or the Tailscale path is offline,
that the server cannot start before manual Keychain enrollment, and that Tailscale Serve and browser
extension enrollment remain external setup.
