"""Audit entry points append valid records without exposing event bodies."""

from datetime import datetime, timedelta
import json
from pathlib import Path

import pytest

from conftest import CliRunner


@pytest.mark.parametrize(
    "kind,event,status,payload",
    [
        ("tool", "PreToolUse", "observed", {"hook_event_name": "PreToolUse"}),
        ("tool", "PostToolUse", "observed", {"hook_event_name": "PostToolUse"}),
        ("tool", "PostToolUse", "observed", {}),
        ("denied", "PermissionDenied", "denied", {}),
        ("denied", "PermissionDenied", "denied", {"hook_event_name": "PermissionDenied"}),
        ("compaction", "PreCompact", "observed", {"trigger": "manual"}),
    ],
)
def test_cli_appends_auditable_jsonl_records(
    *, run_cli: CliRunner, tmp_path: Path, kind: str, event: str, status: str, payload: dict
) -> None:
    for command in ("first", "second"):
        result = run_cli(
            "agents/hooks/audit_log.py",
            kind,
            payload={
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "session_id": "session-one",
                "reason": "requires approval",
                **payload,
            },
        )
        assert result.returncode == 0
        assert result.stdout == result.stderr == ""
    paths = list((tmp_path / "docs/logs/audit").glob("*.jsonl"))
    assert len(paths) == 1
    rows = [json.loads(line) for line in paths[0].read_text().splitlines()]
    assert len(rows) == 2
    for row in rows:
        assert {"ts", "event", "status", "tool", "input", "reason", "session"} <= row.keys()
        assert row["event"] == event
        assert row["status"] == status
        assert row["session"] == "session-one"
        assert row["reason"] == ("requires approval" if kind == "denied" else "")
        assert row["ts"].endswith("Z")
        assert datetime.fromisoformat(row["ts"]).utcoffset() == timedelta(0)
    if kind != "compaction":
        assert [row["input"] for row in rows] == ["first", "second"]


@pytest.mark.parametrize(
    "payload",
    [{"tool_name": "", "tool_input": {}}, {"tool_name": "Bash"}, {"tool_name": "Bash", "tool_input": {"command": ""}}],
)
def test_empty_tool_events_exit_without_a_record(run_cli: CliRunner, tmp_path: Path, payload: dict) -> None:
    result = run_cli("agents/hooks/audit_log.py", "tool", payload=payload)
    assert result.returncode == 0
    assert not list((tmp_path / "docs/logs/audit").glob("*.jsonl"))


def test_unrelated_startup_exits_without_a_record(run_cli: CliRunner, tmp_path: Path) -> None:
    result = run_cli(
        "agents/hooks/audit_log.py", "compaction", payload={"hook_event_name": "SessionStart", "source": "startup"}
    )
    assert result.returncode == 0
    assert not list((tmp_path / "docs/logs/audit").glob("*.jsonl"))


@pytest.mark.parametrize(
    "script,arguments,command,identifier",
    [
        ("guard_command.py", ["forbidden"], "git commit --no-verify -m x", "guard_forbidden_commands.sh"),
        ("guard_dangerous_git.py", [], "git push --force origin main", "guard_dangerous_git.sh"),
    ],
)
def test_real_guard_denials_reach_the_audit_log(
    *, run_cli: CliRunner, tmp_path: Path, script: str, arguments: list[str], command: str, identifier: str
) -> None:
    result = run_cli(
        f"agents/hooks/{script}", *arguments, payload={"tool_input": {"command": command}, "session_id": "session-one"}
    )
    assert result.returncode == 2
    paths = list((tmp_path / "docs/logs/audit").glob("*.jsonl"))
    row = json.loads(paths[0].read_text())
    assert row["event"] == "Blocked"
    assert row["hook"] == identifier
    assert row["tool"] == "Bash"
    assert row["session"] == "session-one"
    assert row["input"] == command
    assert row["reason"]
    if script == "guard_dangerous_git.py":
        assert row["reason"].startswith("BLOCKED:")
