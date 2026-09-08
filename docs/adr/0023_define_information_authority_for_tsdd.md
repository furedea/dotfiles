# ADR-0023: Define information authority for TSDD

- Status: Accepted
- Date: 2026-09-04

In the context of using TSDD across AI coding agents and repositories with executable contracts,
human-facing documentation, automated hooks, and provider-specific entry files, facing a four-part
What/How/Why/Navigation model that treated tests as complete authority, excluded valid prose, and
duplicated VCS policy, we decided for one authoritative source per fact with traceable executable
evidence and explicit ownership across TSDD, Git workflow, ADR, documentation, and automation, and
against assigning every artifact to one exclusive information bucket, to preserve test-first
feedback without confusing Green with complete correctness, accepting that placement decisions
require limited judgment instead of a universal four-row matrix.
