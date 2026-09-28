"""Leaving the sandbox is possible only through a human approval, even in auto mode."""

import json
from pathlib import Path

import pytest

from tests.runtime import CliRunner


ESCAPE_RULE = "Bash(dangerouslyDisableSandbox:true)"


@pytest.fixture(scope="module")
def generated_settings(agent_harness: CliRunner, tmp_path_factory: pytest.TempPathFactory) -> dict:
    path = tmp_path_factory.mktemp("claude-sandbox") / "settings.json"
    agent_harness("generate-claude-settings", "--output", str(path))
    return json.loads(Path(path).read_text())


@pytest.mark.integration
def test_sandbox_escape_is_available(generated_settings: dict) -> None:
    assert generated_settings["sandbox"]["enabled"] is True
    assert generated_settings["sandbox"]["allowUnsandboxedCommands"] is True


@pytest.mark.integration
def test_every_sandbox_escape_asks_the_user(generated_settings: dict) -> None:
    permissions = generated_settings["permissions"]
    assert ESCAPE_RULE in permissions["ask"]
    assert ESCAPE_RULE not in permissions.get("allow", [])
