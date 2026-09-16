"""Command entry points preserve policy discovery, Git context and diagnostics."""

import json
from pathlib import Path
import subprocess

import pytest

from tests.runtime import CliRunner


@pytest.mark.parametrize(
    "kind,pattern,command,status,reason",
    [
        (
            "allowed",
            r"^uv run --frozen --env-file \.env python src/main\.py organize-guidelines( .*)?$",
            "uv run --frozen --env-file .env python src/main.py organize-guidelines run",
            0,
            "Project workflow",
        ),
        (
            "forbidden",
            "^git status --porcelain$",
            "git status --porcelain",
            2,
            "Use the repository status wrapper instead.",
        ),
    ],
)
def test_project_policy_is_combined_with_global_policy(
    *, run_cli: CliRunner, git_project: Path, kind: str, pattern: str, command: str, status: int, reason: str
) -> None:
    policy = git_project / f".agents/hooks/rules/{kind}_commands.json"
    policy.parent.mkdir(parents=True)
    policy.write_text(json.dumps({"version": 1, "rules": [{"patterns": [pattern], "justification": reason}]}))
    result = run_cli("agents/hooks/guard_command.py", kind, payload={"tool_input": {"command": command}})
    assert result.returncode == status
    if status:
        assert reason in result.stderr


@pytest.mark.parametrize(
    "kind,rules",
    [
        ("allowed", []),
        ("forbidden", [{"patterns": ["["], "justification": "Invalid test regex"}]),
    ],
)
def test_invalid_project_rules_cannot_silently_allow_a_command(
    run_cli: CliRunner, git_project: Path, kind: str, rules: list[dict]
) -> None:
    policy = git_project / f".agents/hooks/rules/{kind}_commands.json"
    policy.parent.mkdir(parents=True)
    policy.write_text(json.dumps({"version": 1, "rules": rules}))
    result = run_cli(
        "agents/hooks/guard_command.py", kind, payload={"tool_input": {"command": "uv run --frozen pytest"}}
    )
    assert result.returncode == 2
    assert f"invalid project {kind} command rules" in result.stderr


def test_missing_forbidden_rules_fail_closed(run_cli: CliRunner, tmp_path: Path) -> None:
    result = run_cli(
        "agents/hooks/guard_command.py",
        "forbidden",
        payload={"tool_input": {"command": "git status"}},
        env={"AGENT_FORBIDDEN_COMMAND_RULES": str(tmp_path / "missing.json")},
    )
    assert result.returncode == 2
    assert "forbidden command regex rules were not found or are invalid" in result.stderr


def test_invalid_command_json_remains_a_cli_error(run_cli: CliRunner) -> None:
    result = run_cli("agents/hooks/guard_command.py", "allowed", payload="not json")
    assert result.returncode == 2
    assert "failed to parse" in result.stderr


@pytest.mark.parametrize(
    "script,arguments,command,reason",
    [
        (
            "guard_command.py",
            ("allowed",),
            'uv run --frozen pytest "' + "x" * 1000 + ';literal"',
            "command not in allowlist",
        ),
        ("guard_command.py", ("forbidden",), "rm -rf " + "x" * 1000, "forbidden command"),
        ("guard_git.py", (), "git reset --hard " + "x" * 1000, "BLOCKED:"),
    ],
    ids=["allowlist", "forbidden", "dangerous-git"],
)
def test_command_denial_previews_are_bounded(
    run_cli: CliRunner, script: str, arguments: tuple[str, ...], command: str, reason: str
) -> None:
    result = run_cli(f"agents/hooks/{script}", *arguments, payload={"tool_input": {"command": command}})
    assert result.returncode == 2
    assert reason in result.stderr
    assert "omitted" in result.stderr.lower()
    assert len(result.stderr) < 500


@pytest.mark.parametrize("branch,status", [("main", 2), ("feature/bar", 0), ("feature/foo", 0)])
def test_implicit_push_uses_the_real_repository_branch(
    run_cli: CliRunner, git_project: Path, branch: str, status: int
) -> None:
    if branch != "main":
        subprocess.run(["git", "switch", "--quiet", "-c", branch], cwd=git_project, check=True)
    result = run_cli("agents/hooks/guard_git.py", payload={"tool_input": {"command": "git push"}})
    assert result.returncode == status
    if status:
        assert "main" in result.stderr
