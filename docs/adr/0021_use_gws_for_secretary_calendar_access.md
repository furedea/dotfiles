# ADR-0021: Use gws for secretary calendar access

- Status: Accepted
- Date: 2026-08-30
- Supersedes: ADR-0020

In the context of a Hermes secretary that reads the single primary Google
calendar managed through Apple Calendar, facing an unapproved third-party
client and a bundled Hermes skill that owns broad OAuth state and unrelated
Workspace access, we decided for the revision-pinned `googleworkspace/cli`
upstream flake with a focused local read-only skill and against `gogcli`, the
bundled Hermes `google-workspace` skill, the broad upstream agent skills, and a
custom Calendar API client, to keep authentication in `gws`, constrain OAuth to
Calendar read-only, and keep personal policy separate from provider mechanics,
accepting that `gws` is pre-1.0 and explicitly not an officially supported
Google product.
