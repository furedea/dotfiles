# ADR-0027: Let Nix own Python entry points

- Status: Accepted
- Date: 2026-09-14

In the context of the Python automation adopted in
[ADR-0026](0026_use_python_for_automation_logic.md), facing repeated handwritten
shell bootstraps and Python-to-shell-to-Python calls, we decided for Nix-owned
interpreter selection and direct shared Python calls, and against maintaining
per-command shell bridges or packaging all editable commands as immutable Python
applications, to reduce runtime indirection without changing the edit-and-apply
workflow, accepting separate deployment lifecycles for editable CLI sources and
Nix-snapshotted agent hooks.

Shell remains appropriate for parent-shell state and minimal Nix-generated
launchers. A subprocess remains appropriate when it provides actual isolation,
such as the verification cache's execution gate, not merely to call another
Python function. Deployed interpreter selection must not depend on a project's
virtual environment; the automation keeps its standard-library-only runtime.
