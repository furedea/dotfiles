---
name: domain-modeling
description: >
    Clarify ambiguous domain terminology, concept boundaries, relationships, state transitions,
    and invariants during requirements or design work. Not needed merely to read existing terms
    or format documentation and ADRs.
---

# Domain Modeling

Build a shared understanding of the domain before encoding assumptions in implementation.
Use this when a material ambiguity appears, including during implementation; it is not a mandatory
phase for every change and does not require a grilling session.

## Clarify the Model

- Investigate relevant code, requirements, and existing vocabulary before asking questions whose
  answers are discoverable. Focus on the concepts affected by the task, not a repository-wide model.
- Identify overloaded terms, different names for the same concept, and distinct concepts hidden
  behind one name. Propose precise terms using the domain's established language.
- Establish the context in which each definition applies. Prefer consistent names within that
  context; preserve legitimate differences across contexts and clarify their mappings rather than
  forcing one global definition. Context boundaries come from domain meaning, not file layout alone.
- Use concrete scenarios to clarify relationships, ownership, identity, lifecycle transitions, and
  conditions that must remain true. Explore only distinctions that can materially affect the task.
- Treat hypothetical scenarios as questions, not new requirements. Do not automatically require
  support for every imagined edge case or turn a recommendation into an accepted decision.
- Compare statements with code and documents. Distinguish current behavior from intended changes;
  an implementation mismatch does not establish which source is correct. Surface consequential
  conflicts for resolution rather than silently choosing an interpretation.

For example, an account closure request may mean ending one user's access, cancelling an
organization's subscription, or erasing personal data. Determine whether these are separate
concepts and what each affects before selecting names or implementation structures.

## Outcomes and Boundaries

Make agreed definitions, relationships, and relevant rules explicit, separating them from proposals,
assumptions, and unresolved questions. Stop when the model is sufficient for the requested decision
or behavior; do not attempt to exhaustively model the business.

Clarifying concepts does not authorize implementation, bulk renaming, public API changes, or
document updates outside the request. If documentation is already in scope, carry it through
without asking for approval on every individual update.

Do not prescribe one class, Entity, or Value Object per concept. The domain model informs design;
it does not mandate a DDD architecture or particular language mechanism.

## Preserve Useful Knowledge

Use `information-authority` when durable placement, duplication, or conflicting authority needs
judgment. Reuse existing authoritative material; do not automatically create `CONTEXT.md` or a
context map when the first term is clarified.

When a glossary is warranted, follow its existing format. Keep definitions concise but sufficient
to distinguish concepts, identify the applicable context, and note easily confused terms where
useful. Include domain-specific meanings, not a general programming tutorial. Do not copy
implementation details or behavioral specifications into the glossary.

Use `adr` to decide whether a significant design choice needs a record and how to write it. Keep
ADR eligibility, placement, naming, and templates there rather than duplicating them here.

When implementation follows, use `tsdd` to turn accepted observable contracts into executable
evidence. Modeling scenarios are candidate examples, not tests or acceptance criteria until their
expected outcomes are grounded in the requirement source.
