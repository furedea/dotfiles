# ADR-0005: Scope Homebrew trust to moshi-hook

- Status: Accepted
- Date: 2026-08-21

In the context of installing Moshi from a third-party Homebrew tap on managed Macs, facing formula
definitions that execute Ruby with the user's privileges, we decided for formula-scoped trust of
`rjyo/moshi/moshi-hook` and against trusting the entire `rjyo/moshi` tap or retaining manual trust,
to keep rebuilds declarative while minimizing the code authorized from that tap, accepting that
future releases published through the trusted formula remain eligible for automatic upgrades.
