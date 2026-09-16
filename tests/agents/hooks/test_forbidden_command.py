"""Prefix and regex denials remain distinct from provider approval decisions."""

import json
from pathlib import Path

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
pytestmark = pytest.mark.usefixtures("isolated_project")


@pytest.mark.parametrize(
    "command,status,reason",
    [
        ("git status", 0, ""),
        ("rm codex/hooks.json", 2, "Do not delete files"),
        ("git rm codex/hooks.json", 2, "Do not remove tracked files"),
        ("git status && rm codex/hooks.json", 2, "rm codex/hooks.json"),
        ("bash -c 'echo hello'", 2, "Do not hide shell commands"),
    ],
)
def test_generated_deny_prefixes(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    status: int,
    reason: str,
) -> None:
    policy = tmp_path / "permissions.json"
    policy.write_text(
        json.dumps(
            {
                "version": 1,
                "rules": [
                    {"decision": "deny", "prefix": ["rm"], "justification": "Do not delete files"},
                    {"decision": "deny", "prefix": ["git", "rm"], "justification": "Do not remove tracked files"},
                    {"decision": "deny", "prefix": ["bash", "-c"], "justification": "Do not hide shell commands"},
                ],
            }
        )
    )
    rules = tmp_path / "rules.json"
    rules.write_text(
        json.dumps(
            {"version": 1, "rules": [{"patterns": ["^never-match-this-command$"], "justification": "Test rule"}]}
        )
    )
    monkeypatch.setenv("AGENT_COMMAND_PERMISSIONS", str(policy))
    monkeypatch.setenv("AGENT_FORBIDDEN_COMMAND_RULES", str(rules))
    assert guard.check("forbidden", {"tool_input": {"command": command}}) == status
    output = capsys.readouterr().err
    if status:
        assert "forbidden command" in output
        assert reason in output
    else:
        assert output == ""


@pytest.mark.parametrize(
    "command",
    [
        ".venv/bin/python -c 'print(1)'",
        "./.venv/bin/python3 scripts/check_project.py",
        "/tmp/project/.venv/bin/python -m pytest",
        "git add .",
        "git add -A",
        "git add --all",
        "ls && git add .",
        "echo ok | xargs -I {} git add -A",
        "git   add   .",
        "git add --all --verbose",
        "git commit --no-verify -m example",
        "git commit -m test --no-verify",
        "git commit -n -m test",
        "git   commit   --no-verify",
        "git -c core.fsmonitor=false add -A",
        "git -c core.fsmonitor=false commit --no-verify -m x",
        "git -C /tmp/project add .",
        "/usr/bin/git add -A",
        "env GIT_PAGER=cat git add --all",
        "timeout 30 git commit -n -m test",
        "find . -name '*.pyc' -delete",
        "find . -type f -exec rm {} +",
        "find . -name x -execdir rm {} +",
    ],
)
def test_global_rules_reject_policy_bypasses(command: str) -> None:
    assert guard.check("forbidden", {"tool_input": {"command": command}}) == 2


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /tmp/example",
        "rm -r build",
        "cargo install ripgrep",
        "npm install -g typescript",
        "uv tool install ruff",
        "uv add --dev pytest",
        "nix profile install nixpkgs#ripgrep",
        "security find-generic-password -s example -w",
        "launchctl bootout gui/501/org.example.agent",
        "gh repo delete owner/repo",
        "gh auth login",
        "mosh example.internal",
        "killall Dock",
    ],
)
def test_global_prefixes_deny_irreversible_or_credential_operations(command: str) -> None:
    assert guard.check("forbidden", {"tool_input": {"command": command}}) == 2


@pytest.mark.parametrize(
    "command",
    ["rm scratch.txt", "git rm agents/old.py", "git worktree remove ../topic", "git stash drop", "find . -name x"],
)
def test_reversible_or_asked_operations_are_not_forbidden(command: str) -> None:
    assert guard.check("forbidden", {"tool_input": {"command": command}}) == 0


def test_global_prefix_rejects_home_manager_activation(capsys: pytest.CaptureFixture[str]) -> None:
    assert guard.check("forbidden", {"tool_input": {"command": "home-manager switch --flake ./#kaito"}}) == 2
    assert "Do not activate Home Manager configurations" in capsys.readouterr().err
