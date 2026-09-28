---
name: adr
description: >
    Use to create, review, update, supersede, or deprecate ADRs under docs/adr/, or when a change
    selects a library, framework, database, protocol, hosting, or tool among real alternatives;
    picks an architectural pattern; sets a durable constraint not obvious from code; or reverses
    a previous decision. Not for local implementation details understandable from the code.
---

# Architecture Decision Records

This skill governs the execution layer for ADRs: deciding whether an ADR is needed, reading the existing decision history, creating or superseding ADR files, and keeping decision prose out of tests and implementation.

Use this together with `tsdd` when the work involves both executable behavior and architectural rationale. `tsdd` owns the methodology; this skill owns the mechanics of recording the decision.

## Core Rule

When a change introduces or reverses a broad project decision that the Decision Test identifies,
create or update an ADR under `docs/adr/` in the same task, before finishing the work rather than
as an optional follow-up.

## Decision Test

Before writing an ADR, ask:

1. Would a future maintainer ask "why this approach instead of the obvious alternative?"
2. Does the Why span multiple files, components, workflows, or future changes?
3. Were meaningful alternatives considered or rejected?
4. Would an inline comment either be too narrow or need to be repeated in several places?

Use these questions to assess significance, not as independent automatic triggers. Create an ADR
for a broad decision that constrains future changes, affects multiple components or workflows, or
is costly to reverse. Merely considering alternatives does not require an ADR for a local,
easily reversible implementation choice; prefer code, tests, or a local comment in that case.

## Repository Inspection

Before creating or changing ADRs:

1. Check whether `docs/adr/` exists.
2. Read existing ADR titles and metadata before choosing a new decision.
3. Search existing ADRs for the topic, chosen option, and rejected alternatives.
4. If an existing ADR already covers the decision, update code/tests to follow it instead of writing a duplicate.
5. If the new decision reverses or materially changes an old one, write a new ADR and mark the old one as superseded.

Use `rg --files docs/adr` and targeted `rg` searches when available.

## File Layout

Store ADRs here:

```text
docs/
└── adr/
    ├── 0001_record_architecture_decisions.md
    ├── 0002_<decision_snake_case>.md
    └── 0003_<decision_snake_case>.md
```

Rules:

- Use one decision per file.
- Use sequential four-digit IDs.
- Never reuse an ID.
- Never delete old ADRs to hide history.
- Follow existing repository naming conventions. Otherwise use underscores between the ID and
  decision words, as shown above. Do not rename existing ADRs solely to normalize filenames.
- Create `docs/adr/` if it does not exist.
- If the repository has no ADRs yet and the task adopts ADRs as a practice, create `0001_record_architecture_decisions.md` first.

## Status Rules

Allowed status values:

- `Proposed`
- `Accepted`
- `Superseded`
- `Deprecated`

Default to `Accepted` when the decision is implemented in the same change. Use `Proposed` only when the user asked for a proposal or no implementation change is being made.

Past ADRs are immutable except for metadata status changes. Do not rewrite the body of an accepted ADR to make it match a new decision.

When reversing a decision:

1. Create a new ADR with the next sequential ID.
2. Add `- Supersedes: ADR-NNNN` to the new ADR metadata.
3. Change the old ADR status to `Superseded`.
4. Keep both ADRs in the same commit or change set.

## Preferred Template

Use the Y-Statement form by default:

```markdown
# ADR-NNNN: <Decision title>

- Status: Accepted
- Date: YYYY-MM-DD

In the context of <use case or situation>, facing <concern or forcing function>, we decided for <chosen option> and against <alternatives considered>, to achieve <quality or benefit gained>, accepting <downside or cost incurred>.
```

For superseding ADRs:

```markdown
# ADR-NNNN: <Decision title>

- Status: Accepted
- Date: YYYY-MM-DD
- Supersedes: ADR-0003

In the context of <use case or situation>, facing <concern or forcing function>, we decided for <chosen option> and against <alternatives considered>, to achieve <quality or benefit gained>, accepting <downside or cost incurred>.
```

Use the longer template only when a Y-Statement would be too compressed:

```markdown
# ADR-NNNN: <Decision title>

- Status: Accepted
- Date: YYYY-MM-DD

## Context

## Decision

## Alternatives Considered

## Consequences
```

## Writing Rules

- Write ADRs in English for public repositories.
- Record Why, not What or How.
- Do not duplicate requirement details or executable behavior evidence. Link to the independent
  requirement source and tests where needed; tests are evidence, not the origin of requirements.
- Do not duplicate implementation details that belong in code and types.
- Name rejected alternatives explicitly.
- State the accepted trade-off plainly.
- Keep the ADR short enough that future agents will actually read it.
- Link to related ADRs only when the relationship changes interpretation.

## Workflow

After [Repository Inspection](#repository-inspection), create or supersede only the necessary ADR
files before finishing, then report the ADR path.

## Non-Goals

Do not create ADRs for:

- Ordinary refactors with no architectural choice.
- Language or framework defaults with no project-specific reason.
- Test cases, acceptance criteria, or behavior specs.
- Local code comments that explain one narrow line or block.
- Scratch planning or TODO lists.
