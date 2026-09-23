#!/usr/bin/env -S python3 -IB
"""Translate pi hook payloads at the boundary to shared hook implementations."""

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
        name="pi",
        tools={
            "bash": "Bash",
            "read": "Read",
            "write": "Write",
            "edit": "Edit",
            "multi_edit": "MultiEdit",
            "notebook_edit": "NotebookEdit",
            "apply_patch": "apply_patch",
            "webfetch": "WebFetch",
            "web_search": "WebSearch",
        },
        events={
            "session-start": "session_start",
            "pre-tool-use": "tool_call",
            "session-end": "session_shutdown",
        },
        compaction_events={"session_before_compact": "PreCompact", "session_compact": "PostCompaction"},
        manifest_env="AGENT_HARNESS_PI_MANIFEST",
        manifest_default=".pi/agent/hooks.json",
    )
)


if __name__ == "__main__":
    sys.exit(ADAPTER.main(sys.argv[1:]))
