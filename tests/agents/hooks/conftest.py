"""Disposable verification records, counted check processes, and Herdr fixtures."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT, StubWriter
from tests.agents.hooks.herdr_runtime import TERMINAL, set_agents


sys.path.insert(0, str(REPO_ROOT / "agents/hooks"))
sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
import session_store


@pytest.fixture
def verification_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = tmp_path.parent / (tmp_path.name + "-state")
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    calls = state / "calls"
    monkeypatch.setenv("VERIFICATION_TEST_CALLS", str(calls))
    return calls


@pytest.fixture
def verification_record(
    git_project: Path, verification_calls: Path, executable: StubWriter
) -> session_store.SessionRecord:
    (git_project / "pyproject.toml").write_text("")
    (git_project / "source.py").write_text("before")
    (git_project / "tests").mkdir()
    (git_project / "tests/test_source.py").write_text("def test_source(): pass")
    executable(
        "uv",
        """
        import os
        from pathlib import Path
        import sys
        with Path(os.environ['VERIFICATION_TEST_CALLS']).open('a') as stream:
            stream.write(str(Path.cwd()) + '\\n')
        failed = os.environ.get('VERIFICATION_TEST_FAIL') == '1'
        print('1 failed' if failed else '1 passed')
        sys.exit(int(failed))
        """,
    )
    return session_store.register(git_project, "codex", "verification-test")


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    session_store.register(root, "codex", "session")
    return root


@pytest.fixture
def herdr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Live agents and panes come from files the test controls."""
    directory = tmp_path / "bin"
    directory.mkdir()
    names = tmp_path / "live_agents.txt"
    set_agents(names, "")
    script = directory / "herdr"
    workspaces = tmp_path / "workspaces.json"
    workspaces.write_text('{"result":{"workspaces":[]}}')
    worktrees = tmp_path / "worktrees.json"
    worktrees.write_text('{"result":{"worktrees":[]}}')
    panes = tmp_path / "panes.json"
    panes.write_text(json.dumps({"result": {"panes": [{"pane_id": "p1", "terminal_id": TERMINAL}]}}))
    script.symlink_to(Path(__file__).with_name("fake_herdr.sh"))
    monkeypatch.setenv("HERDR_TEST_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return names
