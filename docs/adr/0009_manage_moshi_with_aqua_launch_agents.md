# ADR-0009: Manage Moshi with Aqua LaunchAgents

- Status: Accepted
- Date: 2026-08-23
- Supersedes: ADR-0004

In the context of a MacBook Pro providing an always-available Moshi host, facing Homebrew service
restarts that can occur outside the logged-in Aqua session while the login Keychain is unavailable,
we decided for Home Manager-owned Aqua LaunchAgents gated on Keychain pairing with a dormant formula
update trigger and against the Homebrew service, file-backed credentials, automatic Keychain unlock,
or a separate persistent monitor, to preserve Keychain protection while automating safe startup and
upgrades, accepting that Moshi remains unavailable before the user completes a GUI login and that an
update helper may retry temporarily while the Keychain is locked.
