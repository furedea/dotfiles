# ADR-0022: Collect secretary digests from primary sources

- Status: Accepted
- Date: 2026-08-31

In the context of replacing X with useful unattended research and technology
briefings, facing unavailable broad web-search tooling, paid social APIs, and
scheduled sessions that cannot rely on conversational memory, we decided for
separate paper and toolchain Skills that query bounded public endpoints with
`curl`, prioritize primary bibliographic and upstream sources, and keep cutoff
and disposition state inside the local Hermes profile, and against X or other
social feeds, a general news digest, paid search providers, extra API keys, and
automatic external writes, to obtain reproducible and actionable summaries
without another account or credential, accepting maintenance of source
watchlists, conservative request rates, local state, and explicit partial
coverage when a public endpoint is unavailable or rate-limited.
