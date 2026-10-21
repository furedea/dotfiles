"""Disposable verification records, counted check processes, and Herdr fixtures."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT, StubWriter
from tests.agents.hooks.herdr_runtime import TERMINAL


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
    names.write_text("")
    script = directory / "herdr"
    workspaces = tmp_path / "workspaces.json"
    workspaces.write_text('{"result":{"workspaces":[]}}')
    worktrees = tmp_path / "worktrees.json"
    worktrees.write_text('{"result":{"worktrees":[]}}')
    panes = tmp_path / "panes.json"
    panes.write_text(json.dumps({"result": {"panes": [{"pane_id": "p1", "terminal_id": TERMINAL}]}}))
    script.write_text(
        f"#!{sys.executable} -I\n"
        "import json\n"
        "from pathlib import Path\n"
        "import sys\n"
        f"directory = Path({str(tmp_path)!r})\n"
        "if sys.argv[1] == 'pane':\n"
        "    print((directory / 'panes.json').read_text())\n"
        "elif sys.argv[1] != 'agent':\n"
        "    print((directory / f'{sys.argv[1]}s.json').read_text())\n"
        "else:\n"
        "    agents = []\n"
        "    for line in (directory / 'live_agents.txt').read_text().splitlines():\n"
        "        name, workspace, terminal, session = (line.split() + ['', '', ''])[:4]\n"
        "        agents.append({'name': name, 'workspace_id': workspace, 'pane_id': 'p1', 'terminal_id': terminal or 'term_agent', 'agent_session': {'value': session or 'session_agent'}})\n"
        "    print(json.dumps({'result': {'agents': agents}}))\n"
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return names
