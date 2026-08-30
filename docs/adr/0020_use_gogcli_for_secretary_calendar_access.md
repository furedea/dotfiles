# ADR-0020: Use gogcli for secretary calendar access

- Status: Accepted
- Date: 2026-08-30

In the context of a Hermes secretary that reads the single Google calendar
managed through Apple Calendar, facing the bundled Hermes Google Workspace
skill's broad plaintext OAuth token, broken service selection, and unrelated
Gmail and Drive surface, we decided for a revision-pinned `gogcli` release with
a focused local read-only skill and against the bundled skill,
`gws`, `gcalcli`, and a custom Calendar API client, to keep automatic access on
the Calendar read-only scope with JSON output, macOS Keychain token storage, and
untrusted-content wrapping, accepting that `gogcli` is actively maintained but
is not an officially supported Google product and still requires a personal
Google Cloud OAuth client.
