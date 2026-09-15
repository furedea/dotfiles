"""Agent-harness rendering and policy isolation for agent tests."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.runtime import CliRunner, REPO_ROOT


@pytest.fixture(scope="session")
def agent_harness() -> CliRunner:
    """Render the repository's provider configuration with the real harness CLI."""
    executable = shutil.which(os.environ.get("AGENT_HARNESS_BIN", "agent-harness"))
    if executable is None:
        pytest.fail("agent-harness is required for provider integration tests")

    def run(*arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [executable, "--profile", "minimal", *arguments, "--source", str(REPO_ROOT / "agents")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return result

    return run


@pytest.fixture
def isolated_project(isolated_project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Extend the shared project fixture with isolated agent policy discovery."""
    for name in ("CLAUDE_PROJECT_DIR", "AGENT_PROJECT_DIR"):
        monkeypatch.setenv(name, str(isolated_project))
    monkeypatch.setenv("AGENT_COMMAND_PERMISSIONS", str(REPO_ROOT / "agents/command_permissions.json"))
    for kind in ("ALLOWED", "FORBIDDEN"):
        monkeypatch.setenv(
            f"AGENT_{kind}_COMMAND_RULES", str(REPO_ROOT / f"agents/hooks/rules/{kind.lower()}_commands.json")
        )
    return isolated_project
