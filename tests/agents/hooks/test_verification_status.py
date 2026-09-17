"""Status observes current applicability without executing or renewing verification."""

import json
from pathlib import Path
import sys

import pytest

from tests.runtime import CliRunner, REPO_ROOT, StubWriter


sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
import session_store


SCRIPT = "agents/hooks/verification_session.py"


def test_status_is_read_only_before_any_verification(
    run_cli: CliRunner, git_project: Path, tmp_path: Path, executable: StubWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path.parent / (tmp_path.name + "-state")))
    (git_project / "pyproject.toml").write_text("")
    record = session_store.register(git_project, "codex", "status-test")
    (git_project / "source.py").write_text("changed")
    executable("uv", "raise AssertionError('status must not execute checks')")
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in record.directory.rglob("*") if path.is_file()
    }
    directory_time = record.directory.stat().st_mtime_ns
    result = run_cli(SCRIPT, "status", str(record.directory))
    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["state"] == "not_run"
    assert output["worktree"] == str(git_project)
    assert output["checks"][0]["applicability"] == "not_run"
    assert output["checks"][0]["scope"] == "full suite"
    assert len(result.stdout.splitlines()) == 1
    assert record.directory.stat().st_mtime_ns == directory_time
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before} == before


def test_invalid_record_fails_status_with_one_json(run_cli: CliRunner, tmp_path: Path) -> None:
    result = run_cli(SCRIPT, "status", str(tmp_path / "missing"))
    assert result.returncode != 0
    assert json.loads(result.stdout)
    assert len(result.stdout.splitlines()) == 1


@pytest.mark.parametrize("failed", [False, True])
def test_status_preserves_saved_outcome_but_invalidates_changed_inputs(
    verification_record: session_store.SessionRecord,
    verification_calls: Path,
    run_cli: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    failed: bool,
) -> None:
    record = verification_record
    monkeypatch.setenv("VERIFICATION_TEST_FAIL", str(int(failed)))
    (record.root / "source.py").write_text("changed")
    assert run_cli(SCRIPT, "verify", str(record.directory)).returncode == int(failed)
    paths = [record.directory, *record.directory.rglob("*")]
    before = {path: (path.stat().st_mtime_ns, path.read_bytes() if path.is_file() else None) for path in paths}
    outcome = "failed" if failed else "passed"
    current = run_cli(SCRIPT, "status", str(record.directory))
    assert current.returncode == 0
    output = json.loads(current.stdout)
    assert output["state"] == outcome
    assert output["checks"][0]["status"] == outcome
    assert output["checks"][0]["applicability"] == "current"
    assert output["checks"][0]["scope"] == "1 files"
    (record.root / "source.py").write_text("changed again")
    stale = json.loads(run_cli(SCRIPT, "status", str(record.directory)).stdout)
    assert stale["state"] == "stale"
    assert stale["checks"][0]["status"] == outcome
    assert stale["checks"][0]["applicability"] == "stale"
    assert verification_calls.read_text().splitlines() == [str(record.root)]
    assert {path: (path.stat().st_mtime_ns, path.read_bytes() if path.is_file() else None) for path in paths} == before


def test_unselected_saved_checks_are_not_applicable(
    verification_record: session_store.SessionRecord, verification_calls: Path, run_cli: CliRunner
) -> None:
    record = verification_record
    (record.root / "source.py").write_text("changed")
    assert run_cli(SCRIPT, "verify", str(record.directory)).returncode == 0
    (record.root / "source.py").write_text("before")
    result = json.loads(run_cli(SCRIPT, "status", str(record.directory)).stdout)
    assert result["state"] == "not_applicable"
    assert result["checks"][0]["applicability"] == "not_applicable"
    assert len(verification_calls.read_text().splitlines()) == 1


def test_unknown_selection_never_reports_past_success_as_current(
    verification_record: session_store.SessionRecord, verification_calls: Path, run_cli: CliRunner
) -> None:
    record = verification_record
    (record.root / "source.py").write_text("changed")
    assert run_cli(SCRIPT, "verify", str(record.directory)).returncode == 0
    mapping = record.root / ".agents/hooks/rules/related_test_extensions.json"
    mapping.parent.mkdir(parents=True)
    mapping.write_text("{")
    result = run_cli(SCRIPT, "status", str(record.directory))
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["state"] == "unknown"
    assert output["checks"][0]["applicability"] == "unknown"
    assert len(verification_calls.read_text().splitlines()) == 1


@pytest.mark.parametrize("receipt", [[], {"status": "passed"}])
def test_malformed_saved_receipts_fail_the_query(
    verification_record: session_store.SessionRecord, run_cli: CliRunner, receipt: object
) -> None:
    record = verification_record
    record.save_results({"checks": {"corrupt": receipt}})
    result = run_cli(SCRIPT, "status", str(record.directory))
    assert result.returncode != 0
    assert json.loads(result.stdout)
