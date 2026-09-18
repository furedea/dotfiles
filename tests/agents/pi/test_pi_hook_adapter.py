"""pi protocol translation using actual entry points and isolated policy files."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests.runtime import CliRunner, REPO_ROOT


SCRIPT = "agents/pi/hooks/hook_adapter.py"
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
                "paths": ["~/.pi/hooks/hook_adapter.py"],
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
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_project: Path, harness: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", "-b", "main", str(root)], check=True)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return root


@pytest.fixture
def manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "hooks.json"
    monkeypatch.setenv("AGENT_HARNESS_PI_MANIFEST", str(path))
    return path


@pytest.mark.parametrize(
    "arguments",
    [
        ("native", "--help"),
        ("native", "compact"),
        ("audit", "denied"),
        ("paths",),
        ("content",),
        ("dispatch",),
        ("shell", "/tmp/arbitrary-hook"),
    ],
)
def test_usage(run_cli: CliRunner, arguments: tuple[str, ...]) -> None:
    result = run_cli(SCRIPT, *arguments)
    assert result.returncode == 1
    assert "Usage" in result.stderr


def test_missing_registration_blocks_tools_with_pi_decision(run_cli: CliRunner, project: Path) -> None:
    payload = {
        "hook_event_name": "tool_call",
        "session_id": "pi-session",
        "tool_name": "bash",
        "tool_input": {"command": "git status"},
        "cwd": str(project),
    }
    result = run_cli(SCRIPT, "native", "pre-tool-use", payload=payload, cwd=project)
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "Verification" in decision["reason"]


def test_registered_session_allows_tools(run_cli: CliRunner, project: Path) -> None:
    store.register(project, "pi", "pi-session")
    payload = {
        "hook_event_name": "tool_call",
        "session_id": "pi-session",
        "tool_name": "bash",
        "tool_input": {"command": "git status"},
        "cwd": str(project),
    }
    result = run_cli(SCRIPT, "native", "pre-tool-use", payload=payload, cwd=project)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


def test_session_start_registers_the_pi_session(run_cli: CliRunner, project: Path) -> None:
    payload = {
        "hook_event_name": "session_start",
        "source": "startup",
        "session_id": "pi-session",
        "cwd": str(project),
    }
    result = run_cli(SCRIPT, "native", "session-start", payload=payload, cwd=project)
    assert result.returncode == 0
    assert store.session_directory(project, "pi", "pi-session").exists()


@pytest.mark.parametrize("command,blocked", [("git reset --hard", True), ("git status", False)])
def test_shell_git_guard(run_cli: CliRunner, project: Path, command: str, blocked: bool) -> None:
    payload = {"tool_name": "bash", "tool_input": {"command": command}, "cwd": str(project)}
    result = run_cli(SCRIPT, "shell", "git", payload=payload, cwd=project)
    assert result.returncode == (2 if blocked else 0)
    if blocked:
        assert "BLOCKED" in result.stderr


@pytest.mark.parametrize(
    "mode,payload,blocked_path",
    [
        ("command", {"tool_name": "bash", "tool_input": {"command": "cat .env"}}, ".env"),
        ("patch", {"tool_name": "write", "tool_input": {"path": "~/.ssh/config"}}, "~/.ssh/config"),
    ],
)
def test_secret_paths_block_with_pi_fields(
    run_cli: CliRunner, harness: Path, mode: str, payload: dict, blocked_path: str
) -> None:
    result = run_cli(SCRIPT, "paths", mode, payload=payload)
    assert result.returncode == 2
    assert blocked_path in result.stderr


def test_input_event_blocks_secret_markers_via_text_field(run_cli: CliRunner, project: Path, harness: Path) -> None:
    payload = {
        "hook_event_name": "input",
        "text": "use fixture-sensitive-marker here",
        "cwd": str(project),
    }
    result = run_cli(SCRIPT, "content", "prompt", payload=payload, cwd=project)
    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == "block"


def test_dispatch_runs_manifest_commands_and_blocks(
    run_cli: CliRunner, project: Path, manifest: Path, tmp_path: Path
) -> None:
    blocker = tmp_path / "blocker.py"
    blocker.write_text(
        "import json, sys\n"
        "payload = json.load(sys.stdin)\n"
        "print(json.dumps({'decision': 'block', 'reason': 'manifest blocked ' + payload['tool_name']}))\n"
    )
    manifest.write_text(
        json.dumps(
            {
                "hooks": {
                    "tool_call": [
                        {
                            "matcher": "^bash$",
                            "hooks": [
                                {"command": f"{sys.executable} {blocker}", "type": "command"},
                            ],
                        }
                    ]
                }
            }
        )
    )
    payload = {
        "hook_event_name": "tool_call",
        "tool_name": "bash",
        "tool_input": {"command": "rm -rf /"},
        "cwd": str(project),
    }

    result = run_cli(SCRIPT, "dispatch", "tool_call", payload=payload, cwd=project)
    assert result.returncode == 0
    assert json.loads(result.stdout)["reason"] == "manifest blocked bash"

    payload["tool_name"] = "read"
    result = run_cli(SCRIPT, "dispatch", "tool_call", payload=payload, cwd=project)
    assert result.returncode == 0
    assert result.stdout == ""


def test_dispatch_propagates_exit_two(run_cli: CliRunner, project: Path, manifest: Path, tmp_path: Path) -> None:
    blocker = tmp_path / "blocker.py"
    blocker.write_text("import sys\nprint('nope', file=sys.stderr)\nsys.exit(2)\n")
    manifest.write_text(
        json.dumps(
            {"hooks": {"tool_call": [{"hooks": [{"command": f"{sys.executable} {blocker}", "type": "command"}]}]}}
        )
    )

    result = run_cli(SCRIPT, "dispatch", "tool_call", payload={}, cwd=project)
    assert result.returncode == 2
    assert "nope" in result.stderr
