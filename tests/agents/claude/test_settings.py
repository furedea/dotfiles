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
