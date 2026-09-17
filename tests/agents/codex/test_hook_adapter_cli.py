"""Codex protocol translation using actual entry points and isolated policy files."""

import json
from pathlib import Path
import shutil

import pytest

from tests.runtime import CliRunner, REPO_ROOT, StubWriter


SCRIPT = "agents/codex/hooks/hook_adapter.py"


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
                "paths": ["~/.codex/hooks/adapt_shell_command.sh"],
            }
        )
    )
    shutil.copyfile(REPO_ROOT / "agents/hooks/rules/secret_path_policy.json", rules / "secret_path_policy.json")
    (rules / "secret_content_patterns.json").write_text(
        json.dumps(
            {
                "fixture": {"pattern": "fixture-sensitive-marker", "message": "Fixture detected"},
            }
        )
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_HARNESS_ROOT", str(root))
    for name in ("AGENT_PROTECTED_PATH_POLICY", "AGENT_SECRET_PATH_POLICY", "AGENT_SECRET_CONTENT_PATTERNS"):
        monkeypatch.delenv(name, raising=False)
    return root


def patch_payload(*paths: str) -> dict:
    return {
        "tool_input": {
            "command": "*** Begin Patch\n"
            + "".join(f"*** Update File: {path}\n@@\n-old\n+new\n" for path in paths)
            + "*** End Patch\n"
        }
    }


@pytest.mark.parametrize(
    "arguments",
    [("harness", "--help"), ("lint", "--help"), ("paths",), ("content",), ("shell", "/tmp/arbitrary-hook")],
)
def test_usage(run_cli: CliRunner, arguments: tuple[str, ...]) -> None:
    result = run_cli(SCRIPT, *arguments)
    assert result.returncode == 1
    assert "Usage" in result.stderr


@pytest.mark.parametrize(
    "paths,blocked",
    [
        (("agents/hooks/guard_file.py",), False),
        (("src/main.py",), False),
        (("src/main.py", "~/.codex/hooks/adapt_shell_command.sh"), True),
    ],
)
def test_harness_patch_paths(run_cli: CliRunner, harness: Path, paths: tuple[str, ...], blocked: bool) -> None:
    result = run_cli(SCRIPT, "harness", payload=patch_payload(*paths))
    assert result.returncode == (2 if blocked else 0)
    if blocked:
        assert "BLOCKED" in result.stderr and ".codex/hooks/adapt_shell_command.sh" in result.stderr
    else:
        assert result.stdout == result.stderr == ""


def test_harness_defaults_to_home(run_cli: CliRunner, harness: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(harness))
    monkeypatch.delenv("AGENT_HARNESS_ROOT")
    result = run_cli(SCRIPT, "harness", payload=patch_payload("~/.codex/hooks/adapt_shell_command.sh"))
    assert result.returncode == 2
    assert "agent harness boundary" in result.stderr


@pytest.mark.parametrize(
    "mode,filename,payload",
    [
        (("harness",), "protected_paths.json", patch_payload("src/main.py")),
        (("paths", "command"), "secret_path_policy.json", {"tool_input": {"command": "cat README.md"}}),
    ],
)
def test_missing_policy_fails_closed(
    run_cli: CliRunner, harness: Path, mode: tuple[str, ...], filename: str, payload: dict
) -> None:
    (harness / ".claude/hooks/rules" / filename).unlink()
    result = run_cli(SCRIPT, *mode, payload=payload)
    assert result.returncode == 2
    assert "BLOCKED" in result.stderr


@pytest.mark.parametrize(
    "mode,payload,blocked_path",
    [
        ("command", {"tool_input": {"command": "cat .env"}}, ".env"),
        ("command", {"tool_input": {"command": "cat ~/.docker/config.json"}}, "~/.docker/config.json"),
        ("command", {"tool_input": {"command": "rg token README.md"}}, ""),
        ("patch", patch_payload(".env.local"), ".env.local"),
        ("patch", {"tool_input": {"file_path": "~/.ssh/config"}}, "~/.ssh/config"),
    ],
)
def test_secret_paths(run_cli: CliRunner, harness: Path, mode: str, payload: dict, blocked_path: str) -> None:
    result = run_cli(SCRIPT, "paths", mode, payload=payload)
    assert result.returncode == (2 if blocked_path else 0)
    if blocked_path:
        assert "BLOCKED" in result.stderr and blocked_path in result.stderr
    else:
        assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("field", ["command", "cmd"])
def test_heredoc_denial_omits_the_body(run_cli: CliRunner, harness: Path, field: str) -> None:
    command = "uv run --frozen python - <<'PY'\n" + "print('body_must_not_be_repeated')\n" * 100 + "PY\n"
    result = run_cli(SCRIPT, "paths", "command", payload={"tool_input": {field: command}})
    assert result.returncode == 2
    assert "heredoc" in result.stderr.lower()
    assert "uv run --frozen python" in result.stderr
    assert "omitted" in result.stderr.lower()
    assert "body_must_not_be_repeated" not in result.stderr
    assert len(result.stderr) < 500


def test_long_command_denial_has_a_bounded_preview(run_cli: CliRunner, harness: Path) -> None:
    command = "echo " + "x" * 1000 + " $uninspectable_variable"
    result = run_cli(SCRIPT, "paths", "command", payload={"tool_input": {"cmd": command}})
    assert result.returncode == 2
    assert "BLOCKED:" in result.stderr
    assert "echo " in result.stderr
    assert "omitted" in result.stderr.lower()
    assert len(result.stderr) < 500


@pytest.mark.parametrize("field", ["command", "cmd"])
@pytest.mark.parametrize("command,blocked", [("git reset --hard", True), ("git status", False)])
def test_shell_payload_fields(run_cli: CliRunner, field: str, command: str, blocked: bool) -> None:
    result = run_cli(SCRIPT, "shell", "git", payload={"tool_input": {field: command}})
    assert result.returncode == (2 if blocked else 0)
    if blocked:
        assert "BLOCKED" in result.stderr and command in result.stderr
    else:
        assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("fail", [True, False])
def test_lint_resolves_payload_cwd_and_suppresses_noise(
    run_cli: CliRunner, tmp_path: Path, executable: StubWriter, fail: bool
) -> None:
    executable(
        "ruff",
        """
        import os, sys
        if "--output-format=concise" in sys.argv and os.environ["LINT_FIXTURE_FAIL"] == "1":
            print("ruff: F821 undefined name")
            sys.exit(1)
        print("environment noise", file=sys.stderr)
    """,
    )
    project = tmp_path / "nested"
    project.mkdir()
    (project / "x.py").write_text("x = 1\n")
    payload = patch_payload("x.py") | {"cwd": str(project)}
    result = run_cli(SCRIPT, "lint", payload=payload, env={"LINT_FIXTURE_FAIL": str(int(fail))})
    assert result.returncode == 0
    assert result.stderr == ""
    if fail:
        row = json.loads(result.stdout)
        assert row["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "F821" in row["hookSpecificOutput"]["additionalContext"]
        assert str(project / "x.py") in row["hookSpecificOutput"]["additionalContext"]
    else:
        assert result.stdout == ""
    assert "environment noise" not in result.stdout


@pytest.mark.parametrize(
    "mode,text,blocked",
    [
        ("prompt", "fixture-sensitive-marker", True),
        ("prompt", "safe prompt", False),
        (
            "apply-patch",
            "*** Begin Patch\n*** Update File: x.txt\n@@\n-old\n+fixture-sensitive-marker\n*** End Patch",
            True,
        ),
        (
            "apply-patch",
            "*** Begin Patch\n*** Update File: x.txt\n@@\n-fixture-sensitive-marker\n+safe\n*** End Patch",
            False,
        ),
    ],
)
def test_content_translation(run_cli: CliRunner, harness: Path, mode: str, text: str, blocked: bool) -> None:
    payload = {"prompt": text} if mode == "prompt" else {"tool_input": {"command": text}}
    result = run_cli(SCRIPT, "content", mode, payload=payload)
    assert result.returncode == 0
    assert result.stderr == ""
    if blocked:
        decision = json.loads(result.stdout)
        assert "Fixture detected" in result.stdout
        if mode == "prompt":
            assert decision["decision"] == "block"
        else:
            assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    else:
        assert result.stdout == ""
