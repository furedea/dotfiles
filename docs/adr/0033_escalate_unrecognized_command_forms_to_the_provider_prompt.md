# ADR-0033: Escalate unrecognized command forms to the provider prompt

- Status: Accepted
- Date: 2026-10-15

In the context of the command and verification hooks from
[ADR-0031](0031_permit_agent_commands_by_reversibility.md) and
[ADR-0029](0029_register_verification_in_native_hooks.md), facing audit evidence that about half
of all hook denials were commands inside an approved family whose exact form the precise rules did
not list or commands the static shell inspection could not decode, and a scope check that denied
the provider's own scratch directory, we decided for returning the provider's `ask` decision in
those cases, treating the session temporary directories as inside the verification scope, and
keeping exit-code denials only for deny prefixes, forbidden patterns, dangerous Git operations,
secret policies, invalid policy files, and missing verification registration, and against widening
the precise allow rules form by form or keeping every mismatch a hard denial, to let the user rather
than the model settle an unusual form while ordinary forms still run without a prompt, accepting
that providers whose hooks cannot prompt still receive a denial for the same cases, and that the
prompt depends on the provider honoring a hook `ask` over its own allow rules.
