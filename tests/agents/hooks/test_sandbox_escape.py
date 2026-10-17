"""No agent command leaves the sandbox; only the excluded tools run outside it."""

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
def test_the_sandbox_escape_is_closed(generated_settings: dict) -> None:
    assert generated_settings["sandbox"]["enabled"] is True
    assert generated_settings["sandbox"]["allowUnsandboxedCommands"] is False


@pytest.mark.integration
def test_an_escape_request_would_still_ask_if_the_runtime_honored_it(generated_settings: dict) -> None:
    permissions = generated_settings["permissions"]
    assert ESCAPE_RULE in permissions["ask"]
    assert ESCAPE_RULE not in permissions.get("allow", [])
