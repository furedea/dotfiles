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
from tests.agents.hooks.cleanup_worktrees_runtime import git

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


@pytest.fixture
def primary(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git("init", "--quiet", "--initial-branch=main", cwd=root)
    git("config", "user.email", "test@example.com", cwd=root)
    git("config", "user.name", "Test", cwd=root)
    git("config", "commit.gpgsign", "false", cwd=root)
    (root / "README.md").write_text("base\n")
    git("add", "README.md", cwd=root)
    git("commit", "--quiet", "-m", "base", cwd=root)
    return root


@pytest.fixture
def merged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Fake gh and Herdr: merged PR heads come from this dict; Herdr records removals."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude/settings.json").write_text('{"sandbox":{"filesystem":{"allowWrite":[]}}}')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "sandbox-tmp"))
    directory = tmp_path / "bin"
    directory.mkdir()
    state = tmp_path / "merged.json"
    removed = tmp_path / "herdr_removed.txt"
    (directory / "gh").write_text(f"#!/bin/sh\ncat {state}\n")
    listing = tmp_path / "herdr_worktrees.json"
    listing.write_text('{"result":{"worktrees":[]}}')
    (tmp_path / "herdr_workspaces.json").write_text('{"result":{"workspaces":[]}}')
    (tmp_path / "herdr_agents.json").write_text('{"result":{"agents":[]}}')
    (tmp_path / "herdr_panes.json").write_text(
        json.dumps({"result": {"panes": [{"pane_id": "p1", "terminal_id": "term_primary"}]}})
    )
    (directory / "herdr").write_text(
        "#!/bin/sh\n"
        f'if [ "$1 $2" = "pane list" ]; then cat {tmp_path / "herdr_panes.json"}; exit 0; fi\n'
        f'if [ "$1 $2" = "workspace list" ]; then cat {tmp_path / "herdr_workspaces.json"}; exit 0; fi\n'
        f'if [ "$1 $2" = "agent list" ]; then cat {tmp_path / "herdr_agents.json"}; exit 0; fi\n'
        f'if [ "$1 $2" = "workspace close" ]; then echo "$@" >> {removed}; exit 0; fi\n'
        f'if [ "$2" = list ]; then cat {listing}; exit 0; fi\n'
        f'echo "$@" >> {removed}\n'
        f'git worktree remove "$(cat {tmp_path / "herdr_path.txt"})"\n'
    )
    for name in ("gh", "herdr"):
        (directory / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")

    class Heads(dict):
        def __setitem__(self, branch: str, oid: str) -> None:
            super().__setitem__(branch, oid)
            state.write_text(json.dumps([{"headRefName": b, "headRefOid": o} for b, o in self.items()]))

    heads = Heads()
    state.write_text("[]")
    return heads
