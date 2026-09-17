"""Audit summaries retain bounded metadata without recording event bodies."""

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import time

import pytest

from tests.runtime import load_script_module


audit = load_script_module("agents/hooks/audit_log.py", "audit_log")


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit", "NotebookEdit"])
def test_file_events_record_only_a_relative_target(tool: str, tmp_path: Path) -> None:
    entry = audit.record(
        "tool",
        {
            "cwd": str(tmp_path),
            "tool_name": tool,
            "tool_input": {"file_path": str(tmp_path / "file.py"), "content": "private body"},
            "session_id": "session-one",
        },
    )
    assert entry["targets"] == ["file.py"]
    assert entry["provider"] == "claude"
    assert entry["session"] != "session-one"
    assert "private body" not in str(entry)
    assert "file_path" not in entry


def test_codex_patch_events_record_only_patch_targets(tmp_path: Path) -> None:
    entry = audit.record(
        "tool",
        {
            "cwd": str(tmp_path),
            "provider": "codex",
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Begin Patch\n*** Update File: src/main.py\n+secret\n*** End Patch"},
        },
    )
    assert entry["provider"] == "codex"
    assert entry["targets"] == ["src/main.py"]
    assert "secret" not in json.dumps(entry)


def test_multi_edit_targets_are_deduplicated_and_urls_are_not_retained() -> None:
    entry = audit.record(
        "tool",
        {
            "tool_name": "MultiEdit",
            "tool_input": {
                "edits": [
                    {"file_path": "src/main.py"},
                    {"file_path": "src/main.py"},
                    {"file_path": "https://user:password@example.invalid/private"},
                ]
            },
        },
    )
    assert entry["targets"] == ["src/main.py", "external"]
    assert "password" not in json.dumps(entry)


@pytest.mark.parametrize("source", ["startup", "unknown"])
def test_unrelated_session_start_is_not_a_compaction_observation(source: str) -> None:
    assert audit.record("compaction", {"hook_event_name": "SessionStart", "source": source}) is None


def test_denial_does_not_retain_reason_or_command() -> None:
    entry = audit.record(
        "denied",
        {
            "tool_name": "Bash",
            "reason": "requires approval: token=secret-value",
            "tool_input": {"command": "curl https://user:password@example.invalid"},
            "session_id": "session-one",
        },
    )
    assert entry["status"] == "denied"
    assert "reason" not in entry
    assert "input" not in entry
    assert "secret-value" not in str(entry)
    assert "password" not in str(entry)


@pytest.mark.parametrize("tool", ["Bash", "WebFetch", "CustomTool", "Agent"])
def test_unknown_or_body_bearing_tools_record_metadata_only(tool: str) -> None:
    values = {
        "Bash": {"command": "echo secret"},
        "WebFetch": {"url": "https://user:password@example.invalid/private"},
        "CustomTool": {"payload": "secret"},
        "Agent": {"description": "secret task", "subagent_type": "Explore"},
    }[tool]
    entry = audit.record("tool", {"tool_name": tool, "tool_input": values})
    assert entry["tool"] == tool
    assert entry["targets"] == []
    assert "secret" not in str(entry)
    assert "password" not in str(entry)


@pytest.mark.parametrize(
    "event,source,trigger,records,expected_counts",
    [
        ("PreCompact", "", "manual", 4, {"messages": 4, "tool_uses": 3}),
        ("PreCompact", "", "auto", 4, {"messages": 4, "tool_uses": 3}),
        ("SessionStart", "compact", "", 1, {"messages": 1, "tool_uses": 0}),
        ("SessionStart", "resume", "", 4, {"messages": 4, "tool_uses": 3}),
    ],
)
def test_compaction_records_counts_without_transcript_path(
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
    assert row["counts"] == expected_counts
    assert "transcript_path" not in row
    assert str(transcript) not in str(row)


@pytest.mark.parametrize("filename", ["", "missing.jsonl"])
def test_unavailable_transcripts_have_zero_counts(tmp_path: Path, filename: str) -> None:
    assert audit.transcript_counts(str(tmp_path / filename) if filename else "") == {"messages": 0, "tool_uses": 0}


def test_timestamp_is_utc_when_appended(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    audit.append_record(audit.record("tool", {"tool_name": "Bash", "tool_input": {"command": "git status"}}))
    rows = [
        json.loads(line)
        for path in (tmp_path / "state/agent-harness/audit").glob("*/*/*.jsonl")
        for line in path.read_text().splitlines()
    ]
    timestamp = datetime.fromisoformat(rows[0]["ts"].replace("Z", "+00:00"))
    assert timestamp.tzinfo == UTC
    assert timestamp.utcoffset() == timedelta(0)


def test_rotation_keeps_each_audit_file_under_the_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree = tmp_path / "worktree"
    state = tmp_path / "state"
    worktree.mkdir()
    monkeypatch.chdir(worktree)
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setattr(audit, "LOG_LIMIT_BYTES", 600)
    monkeypatch.setattr(audit, "CLEANUP_INTERVAL_SECONDS", 0)
    for _ in range(8):
        audit.append_record(
            audit.record("tool", {"tool_name": "Bash", "session_id": "session", "tool_input": {"command": "true"}}),
            cwd=worktree,
        )
    paths = list((state / "agent-harness/audit").glob("*/*/*.jsonl"))
    assert len(paths) > 1
    assert all(path.stat().st_size <= 600 for path in paths)
    assert all(json.loads(line)["event"] == "PostToolUse" for path in paths for line in path.read_text().splitlines())


def test_retention_and_total_size_limits_are_applied_without_corrupting_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "worktree"
    state = tmp_path / "state"
    worktree.mkdir()
    monkeypatch.chdir(worktree)
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setattr(audit, "TOTAL_LOG_LIMIT_BYTES", 900)
    monkeypatch.setattr(audit, "CLEANUP_INTERVAL_SECONDS", 0)
    for _ in range(12):
        audit.append_record(
            audit.record("tool", {"tool_name": "Bash", "session_id": "session", "tool_input": {"command": "true"}}),
            cwd=worktree,
        )
    paths = list((state / "agent-harness/audit").glob("*/*/*.jsonl"))
    assert sum(path.stat().st_size for path in paths) <= 900
    oldest = paths[0]
    os.utime(oldest, (1, 1))
    audit.prune(now=time.time() + audit.RETENTION_SECONDS + 2)
    assert not oldest.exists()
    assert all(json.loads(line) for path in paths if path.exists() for line in path.read_text().splitlines())
