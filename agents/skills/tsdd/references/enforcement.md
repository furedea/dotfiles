# Enforcement Mechanisms

This reference applies only when the user asks to establish or revise TSDD's development workflow.
Ordinary feature work uses existing mechanisms; it does not require creating hooks, wrappers, or PR
templates. Consider the following mechanisms to make the intended path observable:

- A workflow or wrapper that supports selecting Red or Green-baseline paths without manufacturing
  Red. Determining whether a real contract gap exists still requires judgment.
- Hooks and CI gates for tests, type checks, lint, formatting, and risk-specific evaluation.
- A PR template that records the requirement source, behavior slice, Red or baseline evidence,
  final Green evidence, review needs, and ADR impact.
