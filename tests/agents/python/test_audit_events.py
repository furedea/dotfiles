"""Audit summaries exclude sensitive bodies and irrelevant lifecycle events."""

import pytest

from conftest import load_script_module


audit = load_script_module("agents/hooks/audit_events.py", "audit_events")


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
def test_file_events_record_the_path_without_content(tool: str) -> None:
    entry = audit.record(
        "tool", {"tool_name": tool, "tool_input": {"file_path": "file.py", "content": "private body"}}
    )
    assert entry["input"] == "file.py"
    assert "private body" not in str(entry)


@pytest.mark.parametrize("source", ["startup", "unknown"])
def test_unrelated_session_start_is_not_a_compaction_observation(source: str) -> None:
    assert audit.record("compaction", {"hook_event_name": "SessionStart", "source": source}) is None


def test_denial_reason_is_preserved_separately_from_the_command() -> None:
    entry = audit.record(
        "denied", {"tool_name": "Bash", "reason": "requires approval", "tool_input": {"command": "git push"}}
    )
    assert entry["status"] == "denied"
    assert entry["reason"] == "requires approval"
    assert entry["input"] == "git push"
