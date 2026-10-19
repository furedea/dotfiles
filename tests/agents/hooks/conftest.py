"""Disposable verification records and counted check processes."""

from pathlib import Path
import sys

import pytest

from tests.runtime import REPO_ROOT, StubWriter


sys.path.insert(0, str(REPO_ROOT / "agents/hooks"))
sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
import removal_policy
import session_store


@pytest.fixture(autouse=True)
def temporary_roots(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep each test's project outside the roots rm may clear, wherever pytest puts its directories."""
    roots = tmp_path_factory.mktemp("temporary-roots")
    for name in ("tmp", "scratch"):
        (roots / name).mkdir()
    monkeypatch.setenv("TMPDIR", str(roots / "tmp"))
    monkeypatch.setattr(removal_policy, "SCRATCH_ROOT", roots / "scratch")
    return roots


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
