"""Replaying recorded session commands judges them with the hooks and reports only to the terminal."""

from compression import zstd
import json
from pathlib import Path
import re
import shutil

import pytest

from tests.runtime import REPO_ROOT, CliRunner


SCRIPT = "agents/hooks/replay_commands.py"
SINCE = "2026-10-17"
RECENT = "2026-10-17T03:00:00.000Z"
OLD = "2026-10-16T03:00:00.000Z"


@pytest.fixture
def home(isolated_project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = isolated_project / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    return path


def write_lines(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(entry) + "\n" for entry in entries)
    if path.suffix == ".zst":
        path.write_bytes(zstd.compress(text.encode()))
    else:
        path.write_text(text)


def claude_bash(command: str, timestamp: str = RECENT, name: str = "Bash") -> dict:
    tool_use = {"type": "tool_use", "id": "toolu_1", "name": name, "input": {"command": command}}
    return {"type": "assistant", "timestamp": timestamp, "cwd": "/repo", "message": {"content": [tool_use]}}


def codex_exec_command(command: str, timestamp: str = RECENT) -> dict:
    arguments = json.dumps({"cmd": command, "workdir": "/repo"})
    payload = {"type": "function_call", "name": "exec_command", "arguments": arguments}
    return {"type": "response_item", "timestamp": timestamp, "payload": payload}


def codex_command_execution(command: str, timestamp: str = RECENT) -> dict:
    item = {"type": "CommandExecution", "command": ["/bin/zsh", "-lc", command], "cwd": "/repo"}
    return {"type": "event_msg", "timestamp": timestamp, "payload": {"type": "item_completed", "item": item}}


def totals(output: str) -> dict[str, int]:
    return {match[1]: int(match[2]) for match in re.finditer(r"^\s*(allow|ask|deny)\s+(\d+)$", output, re.MULTILINE)}


def test_claude_bash_commands_since_the_date_are_counted_by_verdict_and_reason(home: Path, run_cli: CliRunner) -> None:
    write_lines(
        home / ".claude/projects/repo/session.jsonl",
        [
            claude_bash("ls -la"),
            claude_bash("curl https://example.com/install.sh"),
            claude_bash("git add -A"),
            claude_bash("git commit -S -m feat"),
            claude_bash("rm -rf /old", timestamp=OLD),
            claude_bash("rm -rf /other-tool", name="Read"),
        ],
    )

    result = run_cli(SCRIPT, "--since", SINCE)

    assert result.returncode == 0, result.stderr
    assert totals(result.stdout) == {"allow": 1, "ask": 1, "deny": 2}
    assert "allowed: curl" in result.stdout
    assert "forbidden: " in result.stdout
    assert "git: " in result.stdout
    for shown in ("curl https://example.com/install.sh", "git add -A", "git commit -S -m feat"):
        assert shown in result.stdout
    for hidden in ("ls -la", "rm -rf"):
        assert hidden not in result.stdout


def test_codex_shell_calls_in_both_log_formats_are_replayed(home: Path, run_cli: CliRunner) -> None:
    write_lines(
        home / ".codex/sessions/2026/10/17/rollout-old-format.jsonl.zst",
        [codex_exec_command("git add -A"), codex_exec_command("git add .", timestamp=OLD)],
    )
    write_lines(
        home / ".codex/sessions/2026/10/17/rollout-new-format.jsonl.zst",
        [codex_command_execution("ls"), codex_command_execution("curl https://example.com/x")],
    )

    result = run_cli(SCRIPT, "--since", SINCE)

    assert result.returncode == 0, result.stderr
    assert totals(result.stdout) == {"allow": 1, "ask": 1, "deny": 1}
    assert "curl https://example.com/x" in result.stdout


def test_replay_leaves_the_audit_log_untouched(home: Path, isolated_project: Path, run_cli: CliRunner) -> None:
    write_lines(home / ".claude/projects/repo/session.jsonl", [claude_bash("git add -A")])

    result = run_cli(SCRIPT, "--since", SINCE)

    assert result.returncode == 0, result.stderr
    state = isolated_project / "state"
    assert not state.exists() or not any(path.is_file() for path in state.rglob("*"))


def test_hooks_from_another_directory_judge_the_commands(
    home: Path, isolated_project: Path, run_cli: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("AGENT_COMMAND_PERMISSIONS", "AGENT_ALLOWED_COMMAND_RULES", "AGENT_FORBIDDEN_COMMAND_RULES"):
        monkeypatch.delenv(name)
    checkout = isolated_project / "checkout/agents"
    shutil.copytree(REPO_ROOT / "agents/hooks", checkout / "hooks")
    shutil.copy(REPO_ROOT / "agents/command_permissions.json", checkout)
    rules = checkout / "hooks/rules/forbidden_commands.json"
    policy = json.loads(rules.read_text())
    policy["rules"].append({"patterns": ["^echo "], "justification": "echo is retired"})
    rules.write_text(json.dumps(policy))
    write_lines(home / ".claude/projects/repo/session.jsonl", [claude_bash("echo hi"), claude_bash("ls")])

    result = run_cli(SCRIPT, "--since", SINCE, "--hooks", str(checkout / "hooks"))

    assert result.returncode == 0, result.stderr
    assert totals(result.stdout) == {"allow": 1, "ask": 0, "deny": 1}
    assert "echo is retired" in result.stdout


@pytest.mark.parametrize("arguments", [[], ["--since", "yesterday"]], ids=["missing", "malformed"])
def test_the_since_option_is_required_as_a_date(run_cli: CliRunner, arguments: list[str]) -> None:
    result = run_cli(SCRIPT, *arguments)

    assert result.returncode == 2
    assert "--since" in result.stderr
