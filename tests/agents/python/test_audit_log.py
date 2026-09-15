"""Audit summaries exclude sensitive bodies and irrelevant lifecycle events."""

import pytest
import json
from pathlib import Path

from conftest import load_script_module


audit = load_script_module("agents/hooks/audit_log.py", "audit_log")


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


@pytest.mark.parametrize("kind", ["tool", "denied"])
@pytest.mark.parametrize(
    "tool,values,expected",
    [
        ("Bash", {"command": "git status"}, "git status"),
        ("Edit", {"file_path": "/src/main.py"}, "/src/main.py"),
        ("Write", {"file_path": "/src/new.py"}, "/src/new.py"),
        ("WebFetch", {"url": "https://example.com/api"}, "https://example.com/api"),
        ("CustomTool", {"foo": "bar"}, '{"foo":"bar"}'),
    ],
)
def test_tool_summaries_preserve_only_the_relevant_input(kind: str, tool: str, values: dict, expected: str) -> None:
    row = audit.record(kind, {"tool_name": tool, "tool_input": values})
    assert row["tool"] == tool
    assert row["input"] == expected


@pytest.mark.parametrize(
    "values,expected",
    [
        ({"subagent_type": "Explore", "description": "find API endpoints"}, "Explore: find API endpoints"),
        ({"description": "research task"}, "general-purpose: research task"),
    ],
)
def test_agent_observations_use_a_compact_description(values: dict, expected: str) -> None:
    assert audit.record("tool", {"tool_name": "Agent", "tool_input": values})["input"] == expected


@pytest.mark.parametrize(
    "event,source,trigger,records,expected_counts",
    [
        ("PreCompact", "", "manual", 4, {"messages": 4, "tool_uses": 3}),
        ("PreCompact", "", "auto", 4, {"messages": 4, "tool_uses": 3}),
        ("SessionStart", "compact", "", 1, {"messages": 1, "tool_uses": 0}),
        ("SessionStart", "resume", "", 4, {"messages": 4, "tool_uses": 3}),
    ],
)
def test_compaction_records_preserve_transcript_counts_and_context(
    *, tmp_path: Path, event: str, source: str, trigger: str, records: int, expected_counts: dict
) -> None:
    transcript = tmp_path / "transcript.jsonl"
    contents = [
        {"type": "user", "message": {"content": [{"type": "text", "text": "hi"}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use"}, {"type": "tool_use"}]}},
    ]
    transcript.write_text("\n".join(json.dumps(row) for row in contents[:records]) + "\n")
    row = audit.record(
        "compaction",
        {
            "hook_event_name": event,
            "source": source,
            "trigger": trigger,
            "session_id": "sess-one",
            "transcript_path": str(transcript),
        },
    )
    assert row["event"] == event
    assert row["source"] == source
    assert row["trigger"] == trigger
    assert row["session"] == "sess-one"
    assert row["tool"] == "Compaction"
    assert row["input"] == row["transcript_path"] == str(transcript)
    assert row["counts"] == expected_counts


@pytest.mark.parametrize("filename", ["", "missing.jsonl"])
def test_unavailable_transcripts_have_zero_counts(tmp_path: Path, filename: str) -> None:
    assert audit.transcript_counts(str(tmp_path / filename) if filename else "") == {"messages": 0, "tool_uses": 0}
