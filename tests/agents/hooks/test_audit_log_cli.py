"""Audit entry points append bounded metadata without exposing event bodies."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import CliRunner, REPO_ROOT


def audit_paths(state: Path) -> list[Path]:
    return list((state / "agent-harness/audit").glob("*/*/*.jsonl"))


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
def test_cli_appends_metadata_to_external_jsonl(
    *, run_cli: CliRunner, tmp_path: Path, kind: str, event: str, status: str, payload: dict
) -> None:
    for command in ("first-secret", "second-secret"):
        result = run_cli(
            "agents/hooks/audit_log.py",
            kind,
            "codex",
            payload={
                "cwd": str(tmp_path / "worktree"),
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "session_id": "session-one",
                "reason": "requires approval token=secret-value",
                **payload,
            },
        )
        assert result.returncode == 0
        assert result.stdout == result.stderr == ""
    paths = audit_paths(tmp_path / "state")
    assert len(paths) == 1
    rows = [json.loads(line) for line in paths[0].read_text().splitlines()]
    assert len(rows) == 2
    for row in rows:
        assert {"ts", "event", "status", "provider", "tool", "targets", "session", "worktree"} <= row.keys()
        assert row["event"] == event
        assert row["status"] == status
        assert row["provider"] == "codex"
        assert row["session"] != "session-one"
        assert row["ts"].endswith("Z")
        assert "secret-value" not in json.dumps(row)
        assert "first-secret" not in json.dumps(row)
        assert "second-secret" not in json.dumps(row)
    assert not list((tmp_path / "docs/logs/audit").glob("*.jsonl"))


@pytest.mark.parametrize(
    "payload",
    [{"tool_name": "", "tool_input": {}}, {"tool_name": "Bash"}, {"tool_name": "Bash", "tool_input": {"command": ""}}],
)
def test_empty_tool_events_exit_without_a_record(run_cli: CliRunner, tmp_path: Path, payload: dict) -> None:
    result = run_cli("agents/hooks/audit_log.py", "tool", payload=payload)
    assert result.returncode == 0
    assert not audit_paths(tmp_path / "state")


def test_unrelated_startup_exits_without_a_record(run_cli: CliRunner, tmp_path: Path) -> None:
    result = run_cli(
        "agents/hooks/audit_log.py", "compaction", payload={"hook_event_name": "SessionStart", "source": "startup"}
    )
    assert result.returncode == 0
    assert not audit_paths(tmp_path / "state")


@pytest.mark.parametrize(
    "script,arguments,command,identifier",
    [
        ("guard_command.py", ["forbidden"], "git commit --no-verify -m secret-value", "guard_forbidden_commands.sh"),
        ("guard_git.py", [], "git push --force origin secret-value", "guard_dangerous_git.sh"),
    ],
)
def test_real_guard_denials_reach_external_audit_log_without_command_body(
    *, run_cli: CliRunner, tmp_path: Path, script: str, arguments: list[str], command: str, identifier: str
) -> None:
    result = run_cli(
        f"agents/hooks/{script}",
        *arguments,
        payload={
            "cwd": str(tmp_path / "worktree"),
            "tool_input": {"command": command},
            "session_id": "session-one",
        },
    )
    assert result.returncode == 2
    paths = audit_paths(tmp_path / "state")
    assert len(paths) == 1
    row = json.loads(paths[0].read_text())
    assert row["event"] == "Blocked"
    assert row["rule"] == identifier
    assert row["tool"] == "Bash"
    assert row["session"] != "session-one"
    assert "input" not in row
    assert "reason" not in row
    assert "secret-value" not in paths[0].read_text()


def test_audit_write_failure_is_fail_open_and_does_not_change_hook_status(
    run_cli: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    state.write_text("not-a-directory")
    result = run_cli(
        "agents/hooks/audit_log.py",
        "tool",
        payload={"tool_name": "Bash", "tool_input": {"command": "git status"}},
        env={"XDG_STATE_HOME": str(state)},
    )
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


def test_state_symlink_is_not_followed(run_cli: CliRunner, tmp_path: Path) -> None:
    state = tmp_path / "state"
    external = tmp_path / "external"
    external.mkdir()
    state.symlink_to(external, target_is_directory=True)
    result = run_cli(
        "agents/hooks/audit_log.py",
        "tool",
        payload={
            "cwd": str(tmp_path / "worktree"),
            "tool_name": "Bash",
            "tool_input": {"command": "echo secret"},
        },
        env={"XDG_STATE_HOME": str(state)},
    )
    assert result.returncode == 0
    assert not list(external.rglob("*.jsonl"))


def test_parallel_audit_writes_remain_valid_jsonl(tmp_path: Path) -> None:
    script = REPO_ROOT / "agents/hooks/audit_log.py"
    environment = os.environ | {"XDG_STATE_HOME": str(tmp_path / "state")}
    processes = [
        subprocess.Popen(
            [sys.executable, "-I", "-B", str(script), "tool", "claude"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=tmp_path,
            env=environment,
        )
        for _ in range(12)
    ]
    payload = json.dumps(
        {"cwd": str(tmp_path / "worktree"), "tool_name": "Bash", "tool_input": {"command": "echo secret"}}
    )
    for process in processes:
        process.communicate(payload)
        assert process.returncode == 0
    paths = audit_paths(tmp_path / "state")
    rows = [json.loads(line) for path in paths for line in path.read_text().splitlines()]
    assert len(rows) == len(processes)
