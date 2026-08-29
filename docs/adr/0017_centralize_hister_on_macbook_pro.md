# ADR-0017: Centralize Hister on MacBook Pro

- Status: Accepted
- Date: 2026-08-29

In the context of sharing searchable browser history between MacBook Air and MacBook Pro over an
existing Tailscale tailnet, facing duplicated local indexes, intermittent mobile connectivity, and
secrets that must not enter the Nix store, we decided for running one Hister server on MacBook Pro,
binding it to loopback, publishing it through Tailscale Serve, and pointing the Hister clients on
both hosts at that shared HTTPS origin, and against independent per-host servers, direct network
exposure, or a hosted Hister server, to unify history while keeping its index on the home machine,
accepting that indexing is unavailable while MacBook Pro, Hister, or the Tailscale path is offline
and that Tailscale Serve and browser extension enrollment remain external setup.
