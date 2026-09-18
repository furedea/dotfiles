"""Devin protocol translation using actual entry points and isolated policy files."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests.runtime import CliRunner, REPO_ROOT


SCRIPT = "agents/devin/hooks/hook_adapter.py"
VERIFY = REPO_ROOT / "agents/hooks/verification_session.py"
sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
import session_store as store


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    root = tmp_path / "harness"
    home.mkdir()
    rules = root / ".claude/hooks/rules"
    rules.mkdir(parents=True)
    (rules / "protected_paths.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paths": ["~/.devin/hooks/hook_adapter.py"],
            }
        )
    )
    shutil.copyfile(REPO_ROOT / "agents/hooks/rules/secret_path_policy.json", rules / "secret_path_policy.json")
    shutil.copyfile(REPO_ROOT / "agents/hooks/rules/forbidden_commands.json", rules / "forbidden_commands.json")
    shutil.copyfile(REPO_ROOT / "agents/hooks/rules/allowed_commands.json", rules / "allowed_commands.json")
    (rules / "secret_content_patterns.json").write_text(
        json.dumps(
            {
                "fixture": {"pattern": "fixture-sensitive-marker", "message": "Fixture detected"},
            }
        )
    )
    (rules / "command_permissions.json").write_text((REPO_ROOT / "agents/command_permissions.json").read_text())
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_HARNESS_ROOT", str(root))
    for name in (
        "AGENT_PROTECTED_PATH_POLICY",
        "AGENT_SECRET_PATH_POLICY",
        "AGENT_SECRET_CONTENT_PATTERNS",
        "AGENT_COMMAND_PERMISSIONS",
        "AGENT_ALLOWED_COMMAND_RULES",
        "AGENT_FORBIDDEN_COMMAND_RULES",
    ):
        monkeypatch.delenv(name, raising=False)
    return root


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_project: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", "-b", "main", str(root)], check=True)
    monkeypatch.setenv("DEVIN_PROJECT_DIR", str(root))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return root


@pytest.mark.parametrize(
    "arguments",
    [
        ("native", "--help"),
        ("native", "compact"),
        ("audit", "denied"),
        ("paths",),
        ("content",),
        ("shell", "/tmp/arbitrary-hook"),
    ],
)
def test_usage(run_cli: CliRunner, arguments: tuple[str, ...]) -> None:
    result = run_cli(SCRIPT, *arguments)
    assert result.returncode == 1
    assert "Usage" in result.stderr


def test_missing_registration_blocks_tools_with_devin_decision(run_cli: CliRunner, project: Path) -> None:
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "devin-session",
        "tool_name": "exec",
        "tool_input": {"command": "git status"},
    }
    result = run_cli(SCRIPT, "native", "pre-tool-use", payload=payload, cwd=project)
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "Verification" in decision["reason"]


def test_registered_session_allows_tools_via_devin_project_dir(run_cli: CliRunner, project: Path) -> None:
    store.register(project, "devin", "devin-session")
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "devin-session",
        "tool_name": "exec",
        "tool_input": {"command": "git status"},
    }
    result = run_cli(SCRIPT, "native", "pre-tool-use", payload=payload, cwd=project)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


def test_session_start_registers_the_devin_session(run_cli: CliRunner, project: Path) -> None:
    payload = {
        "hook_event_name": "SessionStart",
        "source": "startup",
        "session_id": "devin-session",
    }
    result = run_cli(SCRIPT, "native", "session-start", payload=payload, cwd=project)
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "additionalContext" in output["hookSpecificOutput"]
    assert store.session_directory(project, "devin", "devin-session").exists()


@pytest.mark.parametrize("command,blocked", [("git reset --hard", True), ("git status", False)])
def test_shell_git_guard(run_cli: CliRunner, project: Path, command: str, blocked: bool) -> None:
    payload = {"tool_name": "exec", "tool_input": {"command": command}}
    result = run_cli(SCRIPT, "shell", "git", payload=payload, cwd=project)
    assert result.returncode == (2 if blocked else 0)
    if blocked:
        assert "BLOCKED" in result.stderr


@pytest.mark.parametrize(
    "mode,payload,blocked_path",
    [
        ("command", {"tool_name": "exec", "tool_input": {"command": "cat .env"}}, ".env"),
        ("patch", {"tool_name": "write", "tool_input": {"file_path": "~/.ssh/config"}}, "~/.ssh/config"),
    ],
)
def test_secret_paths(run_cli: CliRunner, harness: Path, mode: str, payload: dict, blocked_path: str) -> None:
    result = run_cli(SCRIPT, "paths", mode, payload=payload)
    assert result.returncode == (2 if blocked_path else 0)
    if blocked_path:
        assert "BLOCKED" in result.stderr and blocked_path in result.stderr


def test_prompt_content_block_uses_devin_decision(run_cli: CliRunner, harness: Path, project: Path) -> None:
    payload = {"hook_event_name": "UserPromptSubmit", "prompt": "fixture-sensitive-marker"}
    result = run_cli(SCRIPT, "content", "prompt", payload=payload, cwd=project)
    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == "block"


def test_write_content_block_uses_devin_decision(run_cli: CliRunner, harness: Path, project: Path) -> None:
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": "devin-session",
        "tool_name": "write",
        "tool_input": {"file_path": "notes.txt", "content": "fixture-sensitive-marker"},
    }
    result = run_cli(SCRIPT, "content", "write", payload=payload, cwd=project)
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"


def test_audit_tool_records_the_devin_provider(
    run_cli: CliRunner, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "devin-session",
        "tool_name": "exec",
        "tool_input": {"command": "git status"},
    }
    result = run_cli(SCRIPT, "audit", "tool", payload=payload, cwd=project)
    assert result.returncode == 0
    records = list((tmp_path / "state/agent-harness/audit").rglob("*.jsonl"))
    assert records
    entry = json.loads(records[0].read_text().splitlines()[-1])
    assert entry["provider"] == "devin"


def test_audit_compaction_records_post_compaction(
    run_cli: CliRunner, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    payload = {
        "hook_event_name": "PostCompaction",
        "session_id": "devin-session",
        "summary": "condensed",
    }
    result = run_cli(SCRIPT, "audit", "compaction", payload=payload, cwd=project)
    assert result.returncode == 0
    records = list((tmp_path / "state/agent-harness/audit").rglob("*.jsonl"))
    assert records
    entry = json.loads(records[0].read_text().splitlines()[-1])
    assert entry["event"] == "PostCompaction"
    assert entry["provider"] == "devin"
