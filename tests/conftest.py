"""Load standalone automation modules without installing a Python package."""

from importlib import util
from collections.abc import Callable
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CliRunner = Callable[..., subprocess.CompletedProcess[str]]
StubWriter = Callable[[str, str], Path]
HarnessRunner = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture(scope="session")
def agent_harness() -> HarnessRunner:
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
def executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StubWriter:
    """Install explicit process-boundary fakes on an isolated PATH."""
    directory = tmp_path / "bin"
    directory.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ["PATH"])

    def write(name: str, source: str) -> Path:
        path = directory / name
        path.write_text(f"#!{sys.executable} -I\n" + textwrap.dedent(source))
        path.chmod(0o700)
        return path

    return write


@pytest.fixture
def git_project(isolated_project: Path) -> Path:
    """Create a disposable repository with a predictable branch and local identity."""
    for arguments in (
        ["init", "--quiet", "-b", "main"],
        ["config", "user.email", "test@example.invalid"],
        ["config", "user.name", "Test"],
        ["config", "commit.gpgsign", "false"],
        ["config", "core.fsmonitor", "false"],
        ["commit", "--quiet", "--allow-empty", "-m", "test fixture"],
    ):
        subprocess.run(["git", *arguments], cwd=isolated_project, check=True, capture_output=True)
    return isolated_project


@pytest.fixture
def isolated_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep policy discovery and audit writes inside the test's project."""
    monkeypatch.chdir(tmp_path)
    for name in ("CLAUDE_PROJECT_DIR", "AGENT_PROJECT_DIR"):
        monkeypatch.setenv(name, str(tmp_path))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("AGENT_COMMAND_PERMISSIONS", str(REPO_ROOT / "agents/command_permissions.json"))
    for kind in ("ALLOWED", "FORBIDDEN"):
        monkeypatch.setenv(
            f"AGENT_{kind}_COMMAND_RULES", str(REPO_ROOT / f"agents/hooks/rules/{kind.lower()}_commands.json")
        )
    return tmp_path


@pytest.fixture
def run_cli(isolated_project: Path) -> CliRunner:
    """Exercise the real isolated Python entry point, never an implicit shell."""

    def run(
        script: str,
        *arguments: str,
        payload: dict | str = "",
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-I", "-B", str(REPO_ROOT / script), *arguments],
            input=json.dumps(payload) if isinstance(payload, dict) else payload,
            cwd=cwd or isolated_project,
            env=os.environ | (env or {}),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )

    return run


def load_script_module(relative_path: str, module_name: str) -> ModuleType:
    """Load a trusted repository module for direct behavior tests."""
    spec = util.spec_from_file_location(module_name, REPO_ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {relative_path}")
    module = util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
