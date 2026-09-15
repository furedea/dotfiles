# Agent verification

The Nix-managed `codex` and `claude` commands register their Git worktree before
starting the provider. Start from the intended worktree, or use `codex -C PATH`.
The baseline includes tracked and nonignored untracked file signatures, including
existing uncommitted edits. Source contents are never copied into verification
state. A branch base, commit, or remote is not needed.

## Automatic execution

| Boundary                   | Behavior                                                                            |
| -------------------------- | ----------------------------------------------------------------------------------- |
| Launcher                   | Persist the baseline before starting the agent; refuse launch if registration fails |
| SessionStart               | Bind the provider session and restore available resume evidence                     |
| PreToolUse                 | Require registration; check the session worktree and explicit mutation paths        |
| PostToolUse                | Run the existing file-level lint/format hooks                                       |
| Stop after edits           | Select and run related tests from changes since launch                              |
| Stop without new inputs    | Reuse success, or report an unchanged failure as unresolved without rerunning it    |
| SessionEnd / launcher exit | Mark the record ended and prune retained state                                      |

The first Stop after changed content runs verification, including a Stop used for
an intermediate response. There is no model-invoked registration or completion
step. Test selection uses `agents/hooks/rules/related_test_defaults.json` and the
project's `.agents/hooks/rules/related_test_extensions.json`. Missing or invalid
required configuration remains unresolved. No matching runner is reported as
skipped, not passed.

The latest receipt for each selected command includes the repository input
fingerprint, harness implementation, execution environment, and executable identity.
Inputs are checked again after execution. Each check defaults to 300 seconds and
the Stop gate has a 540-second execution budget inside its 600-second hook timeout.
`RUN_RELATED_TESTS_TIMEOUT_SECONDS` can set a positive per-check budget up to 540
seconds. A timeout terminates the check's process group and remains unresolved.

Inside a registered agent's shell, explicit verification and retries are available:

```sh
~/.claude/hooks/verification_session.py check
~/.claude/hooks/verification_session.py retry
```

The first command shares Stop evidence; the second reruns selected checks even if
inputs are unchanged, for example after fixing an external dependency. Directly
running `pytest` or another runner does not create a receipt. The branch-relative
`run_verification.py` gate remains available, but it is no longer attached to Stop.

## Storage and retention

Records use `${XDG_STATE_HOME:-$HOME/.local/state}/agent-harness/verification/`:

```text
<worktree-id>/<run-id>/
  baseline.json
  results.json
  logs/<check-id>.log
  .lease
  .lock
```

The baseline stores paths and content/type/mode signatures. Results replace the
previous receipts; obsolete check logs are removed. Each failure log is capped at
1 MiB, with a 100 MiB aggregate log budget. Cleanup runs at launch, Stop, and exit.
It may remove diagnostic logs while preserving the unresolved result itself.
Directories are private to the user, and files are written atomically with mode 0600.

A launcher-held lease protects active records. Ended runs expire after seven days.
Abandoned runs receive an end timestamp when cleanup first observes that their
lease is no longer held. Resume restores the original baseline when available;
expired evidence requires verification of the current project inputs. Clearing
conversation context keeps the baseline and pending results.

## Supported boundary

This policy covers local terminal sessions launched through the managed commands.
Sessions started outside the launcher cannot use the verification hooks. Native
`--worktree`, extra writable directories, background/app-server entry points,
and CLI settings that replace or disable mandatory hooks are rejected. Choose the
worktree before launching; persist other settings in the normal provider config.
Remote sessions require their own registration boundary and are not supported.

The path guard checks observable cwd, file/patch paths, and literal shell directory
changes. It is not a filesystem sandbox and cannot discover every write inside an
arbitrary script. Native provider permissions must enforce the intended write
boundary. External or unsupported symlink inputs fail snapshotting rather than
silently producing reusable evidence.

The rationale is recorded in [ADR-0028](adr/0028_register_verification_before_agent_launch.md).
