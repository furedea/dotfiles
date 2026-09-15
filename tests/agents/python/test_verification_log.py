"""Retention deletes only recognized completed records, never user or active files."""

from pathlib import Path
import time

import pytest
from pytest_mock import MockerFixture

from conftest import load_script_module


logs = load_script_module("agents/hooks/lib/verification_log.py", "verification_log")


def completed(base: Path, name: str, timestamp: int) -> Path:
    directory = base / name
    directory.mkdir()
    (directory / ".complete").write_text(str(timestamp))
    (directory / "1.output.log").write_text("failure details")
    return directory


def test_retention_preserves_active_legacy_and_recent_logs(tmp_path: Path) -> None:
    now = int(time.time())
    expired = completed(tmp_path, "failure-1-old", 1)
    recent = completed(tmp_path, "failure-2-recent", now)
    active, legacy = tmp_path / "failure-3-active", tmp_path / "run.legacy"
    active.mkdir()
    legacy.mkdir()
    logs.prune(tmp_path, now)
    assert not expired.exists()
    assert all(path.is_dir() for path in (recent, active, legacy))


def test_retention_preserves_symlinks_and_unrecognized_contents(tmp_path: Path) -> None:
    custom = completed(tmp_path, "failure-1-custom", 1)
    (custom / "user.txt").touch()
    outside = completed(tmp_path, "outside", 1)
    link = tmp_path / "failure-2-link"
    link.symlink_to(outside, target_is_directory=True)
    logs.prune(tmp_path, int(time.time()))
    assert (custom / "user.txt").is_file()
    assert (outside / ".complete").is_file()
    assert link.is_symlink()


def test_retention_enforces_budget_newest_first(tmp_path: Path, mocker: MockerFixture) -> None:
    now = int(time.time())
    old = completed(tmp_path, "failure-1-old", now)
    new = completed(tmp_path, "failure-2-new", now)
    mocker.patch.object(logs, "size_kib", return_value=60000, autospec=True)
    logs.prune(tmp_path, now)
    assert not old.exists()
    assert new.is_dir()


def test_canonical_worktree_path_separates_same_named_repositories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    roots = [tmp_path / "one/project", tmp_path / "two/project"]
    for root in roots:
        root.mkdir(parents=True)
    first, second = (logs.prepare_directory(root) for root in roots)
    assert first.parent != second.parent
    assert first.parent.name.startswith("project-")
    assert first.stat().st_mode & 0o777 == 0o700


def test_failure_logs_preserve_command_and_diagnostics_separately(tmp_path: Path) -> None:
    logs.write_failure(tmp_path, 1, "command: pytest tests/test_example.py", "assertion failed")
    assert (tmp_path / "1.command.log").read_text() == "command: pytest tests/test_example.py"
    assert (tmp_path / "1.output.log").read_text() == "assertion failed\n"


def test_oversized_output_retains_explicitly_marked_tail(tmp_path: Path) -> None:
    logs.write_failure(tmp_path, 1, "pytest", " " * (logs.OUTPUT_LIMIT_BYTES + 100) + "last failure")
    data = (tmp_path / "1.output.log").read_bytes()
    assert data.startswith(b"[Output truncated;")
    assert data.endswith(b"last failure\n")
    assert len(data) < logs.OUTPUT_LIMIT_BYTES + 100


def test_logs_cannot_become_verification_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert logs.prepare_directory(tmp_path) is None
