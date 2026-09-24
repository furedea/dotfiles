"""Claude session settings shape the environment every agent command and hook inherits."""

import json

from tests.runtime import REPO_ROOT


def test_agent_git_commands_run_without_the_sandboxed_fsmonitor_daemon() -> None:
    environment = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["env"]
    count = int(environment["GIT_CONFIG_COUNT"])
    configured = {
        environment[f"GIT_CONFIG_KEY_{index}"]: environment[f"GIT_CONFIG_VALUE_{index}"] for index in range(count)
    }
    assert configured["core.fsmonitor"] == "false"


def test_model_cannot_escape_the_sandbox_on_its_own() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert sandbox["enabled"] is True
    assert sandbox["allowUnsandboxedCommands"] is False


def test_verification_and_agent_tools_work_without_escaping_the_sandbox() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert {"~/.cache/nix", "~/.cache/uv"} <= set(sandbox["filesystem"]["allowWrite"])
    assert {"gh", "herdr"} <= set(sandbox["excludedCommands"])


def test_sandbox_paths_use_the_home_prefix_the_sandbox_expands() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert [path for path in sandbox["filesystem"]["allowWrite"] if "$" in path] == []
