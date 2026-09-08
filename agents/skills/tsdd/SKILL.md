---
name: tsdd
description: >
    Test-Specification-Driven Development: use when designing behavior specifications or developing
    production code and tests. Defines tests as durable executable evidence of independently
    required observable contracts and applies TDD by behavior slice.
---

# Test-Specification-Driven Development (TSDD)

## Scope

This repository-specific TDD profile governs the methodology layer of day-to-day coding work: how
an independently required contract becomes executable evidence and how implementation grows from
that evidence. It is deliberately language- and provider-agnostic.

Out of scope and delegated elsewhere:

- Language-specific conventions, commands, mock libraries, fixtures, lint rules, assertion style,
  and package managers → the relevant `*-style` skill and project coding rules.
- Branches, commit authorization and boundaries, commit messages, pushes, and pull requests → the
  `git-workflow` skill.
- Project and CI bootstrap before this methodology applies → the relevant `*-init` skill.
- Information authority, durable prose placement, duplication, traceability, temporary briefs, and
  agent entry maps → the `information-authority` skill.
- Changes that introduce, reverse, or review a broad decision or durable constraint → the `adr`
  skill, which owns decision selection, repository inspection, layout, status, supersession,
  templates, and workflow.

If a rule starts feeling like a language-specific command, VCS operation, or ADR procedure, it
belongs in the owning skill rather than here.

## Core Principle

**A test specification is executable test code that durably encodes accepted observable contracts
as evidence derived from an independent requirement source. It is not a separate test-plan
document, the origin of requirements, or proof that the requirements are complete or correct.**

TDD is the operating discipline used to grow the test specification one independently
understandable behavior slice at a time.

A passing suite shows that the selected examples agree with the current implementation. It does not
show that every required behavior was selected, that the requirement source was interpreted
correctly, or that disabled, mocked, and unobserved paths are correct. Preserve a requirement source
outside the test or planned implementation, and apply human review or independent evaluation in
proportion to the risk. This is especially important for AI coding agents, which can make a test
and its implementation agree on the same wrong assumption. TSDD uses executable evidence,
independent sources, types, review, and risk-appropriate verification together: the evidence
supplies fast objective feedback, and the other layers anchor it to the intended system.

## TDD Operating Discipline

### Red eligibility

Before choosing a development path:

1. Identify a requirement source outside the test and planned implementation.
2. State the minimum observable outcome required by that source before arranging test data or
   choosing an implementation.
3. Determine whether current behavior has a real gap from that outcome.

Use an independent requirement source, such as an explicit user request or tracked defect. Apply
the `information-authority` skill when its authoritative home, durable traceability, or relationship
to a conflicting source requires judgment. A test name, proposed implementation, internal
structure, coverage target, or desire to demonstrate TDD does not create a requirement.

- **Gap exists** → Expected outcome → Red → Green → assess Refactor → final Green.
- **No gap exists** → Green baseline → behavior-preserving change → assess Refactor → final Green.

Reuse an existing failing test when it already demonstrates the gap. Never add or tighten an
assertion solely to manufacture Red.

### Behavior slices

A behavior slice is the smallest independently understandable outcome that can be implemented and
verified without bundling an unrelated requirement. At most one independent behavior slice should
be Red at a time.

One slice may require a parameterized test, several assertions that observe the same outcome, or a
small set of tests across boundaries. Split tests when their outcomes can change independently, not
merely because there is more than one assertion or example row.

### Cycle with a contract gap

1. **Select one behavior slice and expected outcome.** Apply the test quality rules before writing
   the test.
2. **Establish Red for that slice.** Use an existing failing test when it proves the gap; otherwise
   add the minimum test or tightly related test set.
3. **Confirm Red for the expected reason.** Use the narrowest gate that supplies the needed
   intermediate observation without hiding known failures.
4. **Write the minimum code to pass.** Prefer the obvious implementation; triangulate with another
   example only when the general rule is still unclear.
5. **Confirm Green for the slice.** Keep unrelated behavior out of the change.
6. **Assess and improve the design while Green.** Inspect changed and nearby code for duplication,
   unclear names, mixed responsibilities, and unnecessary coupling. Refactor when a concrete
   improvement is warranted, then re-run the relevant gate. Do not manufacture edits or speculative
   abstractions merely to perform a Refactor step.
7. **Finish in a coherent verified state.** VCS recording and delivery are governed by the
   `git-workflow` skill.

### Work without a contract gap

1. Establish the relevant Green baseline using existing evidence when available.
2. Add a passing characterization test only when required behavior needs protection.
3. Make the behavior-preserving change.
4. Assess the design and refactor only when a concrete improvement is warranted.
5. Confirm the relevant final Green state.

## Test Quality Rules

- **Name tests for requirements.** Use names that state the independently required behavior rather
  than generic labels such as `test_success` or `test_case_1`.
- **Avoid overspecification.** Protect only independently required observable contracts. Harmless
  wording, formatting, ordering, and internal structure changes should pass unless exact
  representation is itself required.
- **Do not re-test guarantees already enforced elsewhere.** Test a type or parser invariant at its
  creation boundary instead of repeating it at every consumer.
- **Choose risk-appropriate evidence.** Unit tests alone may not prove integration, concurrency,
  performance, security, migration, or operational requirements.

## Test Oracles and Falsification

A test oracle is the basis for deciding whether an observed result is correct. Derive it from the
independent requirement source and observable contract, not from the implementation under test.
Before accepting Green, try to identify a plausible wrong implementation that could still satisfy
the current tests.

- Compare material requirements with the executable evidence and identify required outcomes that
  have no observation. Tests and implementation can otherwise preserve the same omission or
  misunderstanding.
- Start from relevant failure modes, then choose the test layer and observation point that can
  distinguish the required behavior from a plausible failure. Line execution alone is not a
  sufficient oracle.
- Treat mocks, fakes, and stubs as explicit boundary assumptions. They do not demonstrate real
  integration behavior when protocol, configuration, serialization, timing, or dependency failure
  is part of the risk.
- Include negative, boundary, alternate-path, and failure observations when they are required to
  distinguish an incorrect implementation from the intended behavior. A happy-path Green is not
  sufficient evidence for those risks.
- Use independent review in proportion to risk when the same author or agent derived the tests and
  implementation. This section defines the evaluation questions; the repository or runtime review
  mechanism owns how the review is executed.

## Automatic Verification

Treat repository hooks as verification gates. Do not manually repeat successful tests, lint, or
formatting solely to duplicate a hook result.

Run the narrowest relevant test explicitly when an intermediate observation is needed to confirm
Red or Green before proceeding, when diagnosing a failure, or when the hook did not run or does not
cover the required scope. Use the repository's configured final gates rather than inventing a
parallel verification workflow. Report which evidence came from hooks and any known scope limits.

## Type-Driven Design

Types carry compile-time invariants and constraints. They are not a second requirements source;
they make invalid states unrepresentable.

### Patterns

- **Value Objects** wrap primitives with domain constraints. Construct through a validating
  boundary and keep fields immutable.
- **Branded or newtypes** prevent mixing structurally identical but semantically distinct values.
- **Result or Either types** force callers to handle expected success and failure paths.
- **Exhaustive sum types** make unhandled state-machine cases visible to the compiler.
- **Parse, do not validate repeatedly.** Turn raw boundary input into a constrained type once.

Tests still cover behavior that types cannot express, including business rules, ordering, side
effects, integration, concurrency, and external-system interactions.

## Enforcement Mechanisms

This section applies only when the user asks to establish or revise TSDD's development workflow.
Ordinary feature work uses existing mechanisms; it does not require creating hooks, wrappers, or PR
templates. Consider the following mechanisms to make the intended path observable:

- A workflow or wrapper that supports selecting Red or Green-baseline paths without manufacturing
  Red. Determining whether a real contract gap exists still requires judgment.
- Hooks and CI gates for tests, type checks, lint, formatting, and risk-specific evaluation.
- A PR template that records the requirement source, behavior slice, Red or baseline evidence,
  final Green evidence, review needs, and ADR impact.
