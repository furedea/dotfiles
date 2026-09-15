"""Shared process and disposable-project fixtures for repository tests."""

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from tests.runtime import CliRunner, REPO_ROOT, StubWriter


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
    """Keep working files and state writes inside the test's project."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
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
