import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT


sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
import session_store as store


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    (root / "source.py").write_text("before")
    return root


def test_registration_is_private_and_keeps_only_hashes_outside_worktree(repository: Path) -> None:
    run = store.register(repository, "codex", "session")
    assert not run.directory.is_relative_to(repository)
    assert run.directory.parent.parent == store.state_directory()
    assert run.directory.stat().st_mode & 0o777 == 0o700
    baseline = run.directory / "baseline.json"
    assert baseline.stat().st_mode & 0o777 == 0o600
    assert "before" not in baseline.read_text()
    assert run.baseline.changed_paths(store.capture(repository)) == ()


def test_result_replacement_does_not_accumulate_snapshots(repository: Path) -> None:
    run = store.register(repository, "claude", "session")
    for sequence in range(20):
        run.save_results({"checks": {"pytest": {"status": "failed", "input": str(sequence)}}})
    files = {path.name for path in run.directory.iterdir()}
    assert files == {"baseline.json", "results.json", ".lock"}
    assert run.results()["checks"]["pytest"]["input"] == "19"


def test_resume_retains_original_baseline_and_failure(repository: Path) -> None:
    original = store.register(repository, "codex", "session-1")
    original.save_results({**original.results(), "checks": {"pytest": {"status": "failed"}}})
    (repository / "source.py").write_text("changed during original session")
    original.end()
    resumed = store.register(repository, "codex", "session-1", resuming=True)
    assert resumed.directory == original.directory
    assert "ended_at" not in resumed.results()
    assert resumed.baseline.changed_paths(store.capture(repository)) == ("source.py",)
    assert resumed.results()["checks"]["pytest"]["status"] == "failed"


def test_missing_resume_record_requires_full_revalidation(repository: Path) -> None:
    resumed = store.register(repository, "codex", "expired-session", resuming=True)
    assert resumed.results()["revalidate_all"] is True
    assert resumed.results()["checks"] == {}


def test_failure_logs_are_capped_and_replace_previous_output(repository: Path) -> None:
    run = store.register(repository, "codex", "session")
    path = run.write_log("pytest", "x" * (store.LOG_LIMIT_BYTES * 2))
    assert path.stat().st_size <= store.LOG_LIMIT_BYTES
    assert "truncated" in path.read_text()
    assert run.write_log("pytest", "latest failure") == path
    assert path.read_text() == "latest failure"


def test_gc_removes_expired_runs_but_keeps_a_running_hook(repository: Path) -> None:
    ended = store.register(repository, "codex", "ended")
    ended.end(now=1)
    live = store.register(repository, "claude", "live")
    live.end(now=1)
    with live.lock():
        store.prune(now=store.RETENTION_SECONDS + 2)
        assert live.directory.exists()
    assert not ended.directory.exists()


def test_global_log_budget_does_not_erase_failure_status(repository: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "TOTAL_LOG_LIMIT_BYTES", 100)
    runs = [store.register(repository, provider, "session") for provider in ("claude", "codex")]
    for run in runs:
        run.save_results({"checks": {"pytest": {"status": "failed"}}})
        run.write_log("pytest", "x" * 80)
    store.prune()
    assert sum(path.stat().st_size for path in store.state_directory().glob("*/*/logs/*.log")) <= 100
    assert all(run.results()["checks"]["pytest"]["status"] == "failed" for run in runs)


def test_state_symlink_is_not_followed(repository: Path, tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    state = store.state_directory()
    state.parent.mkdir(parents=True)
    state.symlink_to(external, target_is_directory=True)
    with pytest.raises(store.StateError, match="symlink"):
        store.register(repository, "codex", "session")
    assert list(external.iterdir()) == []


def test_another_hook_cannot_enter_the_same_run_lock(repository: Path) -> None:
    run = store.register(repository, "codex", "session")
    with run.lock():
        with (run.directory / ".lock").open("r+") as competing:
            with pytest.raises(BlockingIOError):
                fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_corrupt_evidence_is_an_error_not_an_empty_success(repository: Path) -> None:
    run = store.register(repository, "codex", "session")
    (run.directory / "results.json").write_text(json.dumps({"checks": []}))
    with pytest.raises(store.StateError):
        run.results()


def test_gc_never_follows_a_log_directory_symlink(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = store.register(repository, "codex", "session")
    external = tmp_path / "external-logs"
    external.mkdir()
    important = external / "keep.log"
    important.write_text("must survive")
    (run.directory / "logs").symlink_to(external, target_is_directory=True)
    monkeypatch.setattr(store, "TOTAL_LOG_LIMIT_BYTES", 1)
    store.prune()
    assert important.read_text() == "must survive"


def test_repeated_registration_preserves_baseline_and_does_not_accumulate_records(repository: Path) -> None:
    original = store.register(repository, "codex", "session")
    (repository / "source.py").write_text("changed")
    for _ in range(10):
        repeated = store.register(repository, "codex", "session")
        assert repeated.baseline.changed_paths(store.capture(repository)) == ("source.py",)
    assert list(store.run_directories(store.state_directory())) == [original.directory]


def test_same_session_id_in_different_providers_keeps_independent_baselines(repository: Path) -> None:
    codex = store.register(repository, "codex", "session")
    (repository / "source.py").write_text("codex edit")
    claude = store.register(repository, "claude", "session")
    assert codex.directory != claude.directory
    assert codex.baseline.changed_paths(store.capture(repository)) == ("source.py",)
    assert claude.baseline.changed_paths(store.capture(repository)) == ()


def test_inactive_session_expires_without_session_end_delivery(repository: Path) -> None:
    abandoned = store.register(repository, "codex", "abandoned")
    os.utime(abandoned.directory, (1, 1))
    store.prune(now=store.RETENTION_SECONDS + 2)
    assert not abandoned.directory.exists()


def test_tool_activity_keeps_an_unended_session(repository: Path) -> None:
    live = store.register(repository, "codex", "live")
    os.utime(live.directory, (1, 1))
    live.touch()
    store.prune()
    assert live.directory.exists()
