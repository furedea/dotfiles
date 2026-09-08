---
name: information-authority
description: >
    Governs where durable repository information belongs, which artifact is authoritative for each
    fact, when another artifact may link to, verify, execute, or generate it, and how to avoid
    manually maintained duplication. Load when deciding where durable information belongs,
    resolving duplication or conflict across artifacts, preserving requirement traceability, using
    a temporary implementation brief, or changing an agent entry map such as AGENTS.md or
    CLAUDE.md.
---

# Information Authority

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
- Branches, commits, pushes, and pull requests → the `git-workflow` skill.

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

Mark a repository brief with its temporary status and expiry event, such as task completion, PR
merge, or a stated date. The authoritative source for each relevant fact overrides the brief if the
two conflict.

Before finishing, resolve the brief deliberately. Move each accepted item to the authoritative
location defined under Information Placement, then handle non-authoritative remnants:

- Remaining work → tracked issue or other project work system.
- Work order or obsolete notes → delete, or archive with a clear non-authoritative status when the
  project needs the review history.

Do not let an implementation brief become a second specification.

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
