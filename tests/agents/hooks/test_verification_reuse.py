"""Explicit verify and native Stop share evidence, measured by process invocations."""

import json
from pathlib import Path
import sys

import pytest

from tests.runtime import CliRunner, REPO_ROOT


sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
import session_store


SCRIPT = "agents/hooks/verification_session.py"


@pytest.mark.parametrize("failed", [False, True])
def test_explicit_verify_and_stop_reuse_one_execution(
    verification_record: session_store.SessionRecord,
    verification_calls: Path,
    run_cli: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    failed: bool,
) -> None:
    record = verification_record
    monkeypatch.setenv("VERIFICATION_TEST_FAIL", str(int(failed)))
    (record.root / "source.py").write_text("changed")
    for _ in range(2):
        result = run_cli(SCRIPT, "verify", str(record.directory))
        assert result.returncode == int(failed), result.stdout
    stop = run_cli(SCRIPT, "codex", "stop", payload={"cwd": str(record.root), "session_id": "verification-test"})
    assert "decision" not in json.loads(stop.stdout)
    assert verification_calls.read_text().splitlines() == [str(record.root)]
    assert {value["status"] for value in record.results()["checks"].values()} == {"failed" if failed else "passed"}


@pytest.mark.parametrize("change", ["file", "config", "environment"])
def test_changed_inputs_require_another_execution(
    verification_record: session_store.SessionRecord,
    verification_calls: Path,
    run_cli: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    record = verification_record
    (record.root / "source.py").write_text("changed")
    assert run_cli(SCRIPT, "verify", str(record.directory)).returncode == 0
    if change == "environment":
        monkeypatch.setenv("PYTEST_ADDOPTS", "-x")
    else:
        filename = "source.py" if change == "file" else "pyproject.toml"
        (record.root / filename).write_text("# changed again")
    assert run_cli(SCRIPT, "verify", str(record.directory)).returncode == 0
    assert len(verification_calls.read_text().splitlines()) == 2


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_session_start_notifies_the_registered_path_as_model_context(
    verification_record: session_store.SessionRecord, run_cli: CliRunner, provider: str
) -> None:
    root = verification_record.root
    result = run_cli(
        SCRIPT,
        provider,
        "session-start",
        payload={"cwd": str(root), "session_id": "notified-session", "source": "startup"},
    )
    assert result.returncode == 0
    # Both providers specify SessionStart additionalContext as model-visible input.
    context = json.loads(result.stdout)["hookSpecificOutput"]
    assert context["hookEventName"] == "SessionStart"
    prefix = "Verification record: "
    message = context["additionalContext"]
    assert message.startswith(prefix) and len(message.splitlines()) == 1
    expected = session_store.session_directory(root, provider, "notified-session")
    assert Path(message.removeprefix(prefix)) == expected
    assert session_store.load(expected).results()["session_id"] == "notified-session"


def test_another_session_executes_its_own_checks(
    verification_record: session_store.SessionRecord, verification_calls: Path, run_cli: CliRunner
) -> None:
    first = verification_record
    second = session_store.register(first.root, "codex", "second-session")
    (first.root / "source.py").write_text("changed")
    for record in (first, second):
        assert run_cli(SCRIPT, "verify", str(record.directory)).returncode == 0
    assert len(verification_calls.read_text().splitlines()) == 2


def test_stop_in_another_worktree_cannot_reuse_the_record(
    verification_record: session_store.SessionRecord, verification_calls: Path, run_cli: CliRunner
) -> None:
    record = verification_record
    (record.root / "source.py").write_text("changed")
    assert run_cli(SCRIPT, "verify", str(record.directory)).returncode == 0
    result = run_cli(SCRIPT, "codex", "stop", payload={"cwd": str(REPO_ROOT), "session_id": "verification-test"})
    assert json.loads(result.stdout)["decision"] == "block"
    assert len(verification_calls.read_text().splitlines()) == 1
