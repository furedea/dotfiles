"""Disposable verification records and counted check processes."""

from pathlib import Path
import sys

import pytest

from tests.runtime import REPO_ROOT, StubWriter


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
