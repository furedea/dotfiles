#!/usr/bin/env -S python3 -IB
"""Translate Hermes hook payloads at the boundary to shared hook implementations."""

from pathlib import Path
import sys

SCRIPT = Path(__file__).resolve()
# Deployed adapters live in ~/.<provider>/hooks beside ~/.claude/hooks; the source tree keeps agents/hooks.
COMMON = SCRIPT.parents[2] / (".claude/hooks" if SCRIPT.parent.parent.name.startswith(".") else "hooks")
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(COMMON / "lib"))

import provider_adapter

ADAPTER = provider_adapter.Adapter(
    provider_adapter.Profile(
        name="hermes",
        tools={
            "terminal": "Bash",
            "exec_command": "Bash",
            "shell": "Bash",
            "read_file": "Read",
            "write_file": "Write",
            "edit_file": "Edit",
            "patch": "Edit",
            "apply_patch": "apply_patch",
            "web_search": "WebSearch",
            "fetch_url": "WebFetch",
        },
        events={
            "session-start": "on_session_start",
            "pre-tool-use": "pre_tool_call",
            "stop": "pre_verify",
            "session-end": "on_session_end",
        },
        compaction_events={"on_session_start": "SessionStart"},
        manifest_env="AGENT_HARNESS_HERMES_MANIFEST",
        manifest_default=".hermes/hooks.json",
    )
)


if __name__ == "__main__":
    sys.exit(ADAPTER.main(sys.argv[1:]))
