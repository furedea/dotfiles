---
name: source-of-truth
description: >
    Use when choosing where durable repository information belongs, resolving duplicated or
    conflicting sources, or changing the navigation in AGENTS.md or CLAUDE.md.
---

# Source of Truth

## Scope

This skill governs the information architecture of repository work:

- Selecting one authoritative source for each fact.
- Placing requirements, executable evidence, constraints, implementation, rationale, guidance,
  policy, and navigation in the artifact suited to their purpose.
- Distinguishing useful links, verification, execution, and generated views from manually
  maintained duplication.
- Preserving vocabulary and requirement traceability across artifacts.
- Managing temporary implementation briefs without turning them into a second specification.
- Keeping agent entry maps concise and navigational.

Out of scope and delegated elsewhere:

- Turning an accepted observable contract into executable evidence and applying Red, Green, and
  Refactor → the `tsdd` skill.
- Creating, reviewing, superseding, or deprecating architecture decision records → the `adr`
  skill.
- Language-specific documentation and code conventions → the relevant `*-style` skill and project
  rules.
- Issue publication and comment management → [issue-workflow](../issue-workflow/SKILL.md).
- Git delivery → [git-workflow](../git-workflow/SKILL.md).

Choosing an authoritative location does not by itself authorize creating or editing that artifact.
Follow the user's request and repository-specific rules before making a change.

## Core Principle

Give each fact one authoritative source. Other artifacts may link to it, verify it, execute it, or
be generated mechanically from it. Those relationships are not duplication. Manually maintaining
the same fact in multiple places creates a synchronization risk. Remove it when no distinct purpose
justifies it. When multiple representations must remain, make their authority and synchronization
mechanism explicit.

Avoid manually restating the same internal behavior or implementation facts in prose. Prose is
valid when it has a distinct purpose or audience, such as requirement provenance, decision
rationale, API reference, user guidance, migration guidance, or an operational runbook.

## Information Placement

- **Issue body** → this task's purpose, scope, acceptance criteria, and requirement sources.
- **Plan comment** → this task's implementation approach, major steps, and important assumptions.
  A plan is not the authority for requirements; existing formal specifications and user
  requirements retain their authority under this skill's conflict policy.
- **PR body** → actual changes, verification results, and material departures from the plan.
  Link these artifacts to each other instead of manually maintaining the same details in all three.
- **Requirement purpose, source, scope, or accepted risk** → user request, issue or reproduced
  defect, public interface, external standard, product record, or behavior intentionally preserved
  for compatibility. Preserve a link or identifier when durable traceability matters.
- **Executable evidence of observable behavior** → automated acceptance, integration, or unit test.
  Derive it from an independent requirement source. The source remains authoritative for intent;
  a passing check does not override it. Choose the cheapest level that proves the behavior without
  coupling to implementation details.
- **Quality target or accepted threshold** → measurable acceptance criterion, SLO, product record,
  or security policy. Treat reliability, performance, and security as requirements when they
  constrain the product, not merely when a test command exists.
- **Executable quality evidence** → performance, reliability, or security checks and other
  evaluations. Link each one to the target or threshold it evaluates.
- **Domain invariant or enforceable constraint** → type, Value Object, schema, parser, boundary
  validation, static rule, or configuration. Test runtime behavior that the enforcing mechanism
  does not itself guarantee.
- **Implementation** → code and types whose names and structure express the current design.
- **Broad decision rationale** → ADR. Record alternatives and trade-offs; use an inline comment
  for narrowly local rationale.
- **User or operator guidance** → README, API reference, how-to guide, migration guide, or runbook.
  These serve readers and tasks that tests do not. Generate reference material when practical.
- **Development and verification policy** → skills, hooks, and CI configuration. Keep commands and
  tool-specific mechanics in their owning layer.
- **Agent navigation** → the repository-defined entry map described under Agent Entry Maps.

Domain vocabulary is cross-cutting rather than a separate document by default. Within a bounded
context, use the same terms in code, types, tests, diagrams, and prose. Add a short glossary only
when code cannot communicate the distinctions to every relevant audience.

## Duplication Test

Before creating, copying, or deleting durable information in any artifact, ask:

1. Does it repeat a fact already expressed authoritatively elsewhere?
2. Does it serve a distinct reader or task that the authoritative form cannot serve?
3. Can it link to or be generated from the authoritative source instead of copying it?
4. If both forms must exist, is their authority and synchronization mechanism explicit?

In regulated or contractually controlled work, a natural-language specification may be the legal
authority. Do not silently make tests authoritative over it. Preserve traceability between the
controlling requirement and its executable checks.

## Resolving Conflicts

When artifacts disagree about the same fact:

1. Identify the exact fact, each conflicting representation, and any claimed authority.
2. Determine authority using Information Placement, repository policy, requirement provenance, and
   controlling contractual or legal obligations. Do not infer authority from recency or executable
   form alone.
3. If authority remains ambiguous or controlling sources conflict, preserve the current state,
   report the conflict, and request human judgment instead of silently rewriting either source.
4. After resolution, update the authoritative source if needed, then link, update, or regenerate
   dependent views. Preserve durable traceability when it matters.

## Temporary Implementation Briefs

Natural language may be used as non-authoritative working memory, especially across sessions or for
human review. A temporary implementation brief may record:

- Goal and non-goals.
- Candidate behavior slices and affected boundaries.
- Risks, open questions, and assumptions.
- Planned verification and human review points.
- Decisions still awaiting an authoritative home.

Create local plan files or working notes only when needed for the work. Mark each temporary file
with its corresponding Issue or plan-comment reference and an exit condition, such as task
completion or PR merge. The authoritative source for each fact overrides the brief on conflict.

At completion, move requirements, decisions, and unfinished work needed later to the appropriate
locations under Information Placement. Confirm that preservation succeeded before deleting
task-only work order, checklists, and obsolete notes. Retain notes while work is interrupted or
preservation has failed. User-provided originals and existing permanent documents are never
automatic deletion targets.

Do not require one commit to save a plan and another to delete it. Completed plan comments remain
history, not current instructions for the next task. Do not let a brief become a second
specification. Posting and updating Issue comments belongs to
[issue-workflow](../issue-workflow/SKILL.md#plan-comments).

## Agent Entry Maps

Use the repository-defined agent entry file, such as `AGENTS.md`, `CLAUDE.md`, or a generated
provider equivalent, as a map rather than a textbook. Prefer one canonical source and generate
provider-specific equivalents when multiple files must carry the same instructions.

An entry map may contain:

- A short project summary and directory map.
- Repository-wide constraints and explicit prohibitions.
- Pointers to relevant skills, verification policy, ADRs, and documentation.

It should not copy:

- The complete list of requirements.
- Implementation details.
- Decision rationale already held by ADRs.
- Documentation that changes for every feature.

Keep the canonical entry map concise enough to scan as an entry point. When detail no longer serves
navigation, move it to the appropriate authoritative source and retain a pointer.
