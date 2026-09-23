#!/usr/bin/env -S python3 -IB
"""Translate Devin hook payloads at the boundary to shared hook implementations."""

import os
from pathlib import Path
import sys

SCRIPT = Path(__file__).resolve()
# Deployed adapters live in ~/.<provider>/hooks beside ~/.claude/hooks; the source tree keeps agents/hooks.
COMMON = SCRIPT.parents[2] / (".claude/hooks" if SCRIPT.parent.parent.name.startswith(".") else "hooks")
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(COMMON / "lib"))

import provider_adapter


def project_directory() -> str:
    """Devin omits cwd from hook input and exports the project directory instead."""
    return os.environ.get("DEVIN_PROJECT_DIR") or ""


ADAPTER = provider_adapter.Adapter(
    provider_adapter.Profile(
        name="devin",
        tools={
            "exec": "Bash",
            "read": "Read",
            "write": "Write",
            "edit": "Edit",
            "multi_edit": "MultiEdit",
            "notebook_edit": "NotebookEdit",
            "run_subagent": "Task",
            "webfetch": "WebFetch",
        },
        events={
            "session-start": "SessionStart",
            "pre-tool-use": "PreToolUse",
            "stop": "Stop",
            "session-end": "SessionEnd",
        },
        compaction_events={"SessionStart": "SessionStart", "PostCompaction": "PostCompaction"},
        formatter=provider_adapter.additional_context,
        cwd_fallback=project_directory,
    )
)


if __name__ == "__main__":
    sys.exit(ADAPTER.main(sys.argv[1:]))
