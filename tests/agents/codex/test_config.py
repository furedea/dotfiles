"""Codex sessions get the same sandboxed delivery environment as Claude sessions."""

import json
from pathlib import Path
import tomllib

import pytest

from tests.runtime import REPO_ROOT, CliRunner


CLEANUP_COMMAND = '"$HOME/.claude/hooks/cleanup_worktrees.py" session-start'


def codex_config() -> dict:
    return tomllib.loads((REPO_ROOT / "agents/codex/config.toml").read_text())


def git_config(environment: dict[str, str]) -> dict[str, str]:
    count = int(environment["GIT_CONFIG_COUNT"])
    return {environment[f"GIT_CONFIG_KEY_{index}"]: environment[f"GIT_CONFIG_VALUE_{index}"] for index in range(count)}


def session_start_handlers(hooks: dict) -> list[dict]:
    return [hook for group in hooks["SessionStart"] for hook in group["hooks"]]


def test_codex_writes_the_workspace_inside_the_sandbox() -> None:
    assert codex_config()["sandbox_mode"] == "workspace-write"


def test_codex_sandbox_reaches_the_network_for_push_and_pull_requests() -> None:
    assert codex_config()["sandbox_workspace_write"]["network_access"] is True


def test_codex_keeps_asking_before_leaving_the_sandbox() -> None:
    assert codex_config()["approval_policy"] == "on-request"


def test_codex_git_matches_the_claude_git_environment() -> None:
    claude = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["env"]
    codex = codex_config()["shell_environment_policy"]["set"]
    assert git_config(codex) == git_config(claude)
    assert git_config(codex)["commit.gpgsign"] == "false"


def test_codex_session_start_cleans_merged_worktrees_in_the_background() -> None:
    hooks = json.loads((REPO_ROOT / "agents/hooks.json").read_text())["codex"]["hooks"]
    cleanup = [handler for handler in session_start_handlers(hooks) if handler["command"] == CLEANUP_COMMAND]
    assert len(cleanup) == 1
    assert cleanup[0]["async"] is True


@pytest.mark.integration
def test_generated_codex_config_keeps_the_sandbox_and_git_environment(
    agent_harness: CliRunner, tmp_path: Path
) -> None:
    path = tmp_path / "config.toml"
    agent_harness("generate-codex-config-source", "--output", str(path))
    config = tomllib.loads(path.read_text())
    assert config["sandbox_mode"] == "workspace-write"
    assert config["sandbox_workspace_write"]["network_access"] is True
    assert git_config(config["shell_environment_policy"]["set"])["core.fsmonitor"] == "false"


@pytest.mark.integration
def test_generated_codex_hooks_clean_merged_worktrees_at_session_start(
    agent_harness: CliRunner, tmp_path: Path
) -> None:
    path = tmp_path / "hooks.json"
    agent_harness("generate-codex-hooks", "--output", str(path))
    handlers = session_start_handlers(json.loads(path.read_text())["hooks"])
    assert [
        handler["async"] for handler in handlers if handler["command"].endswith('cleanup_worktrees.py" session-start')
    ] == [True]
