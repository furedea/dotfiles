# ADR-0011: Separate Hermes profile sources from runtime state

- Status: Accepted
- Date: 2026-08-24
- Supersedes: ADR-0010

In the context of a Hermes secretary whose identity, skills, and routine intent
should evolve through reviewed dotfiles while its scheduler continuously writes
execution state, facing profile directories that require official bootstrap and
`cron/jobs.json` fields that change after every run, we decided for creating the
profile through the Hermes CLI, out-of-store linking only SOUL and secretary
Skills, expressing recurring routines as Skill blueprints, and keeping config,
credentials, memory, sessions, and instantiated cron state local, and against
linking the cron directory or constructing a partial profile from nested links,
to preserve editable behavior without versioning runtime churn, accepting that
blueprints must be instantiated locally before they run.
