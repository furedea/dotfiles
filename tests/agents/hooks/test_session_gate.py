import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT, load_script_module


sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
gate = load_script_module("agents/hooks/lib/session_gate.py", "session_gate")
import session_store


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> session_store.Run:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    (root / "pyproject.toml").write_text("")
    (root / "source.py").write_text("preexisting edit")
    (root / "tests").mkdir()
    (root / "tests/test_source.py").write_text("def test_source(): pass")
    binary = tmp_path / "bin"
    binary.mkdir()
    runner = binary / "uv"
    runner.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "with pathlib.Path(os.environ['TEST_CALLS']).open('a') as stream:\n"
        "    stream.write(json.dumps({'cwd': str(pathlib.Path.cwd()), 'argv': sys.argv[1:]}) + '\\n')\n"
        "mode = os.environ.get('TEST_OUTCOME', 'passed')\n"
        "if mode == 'mutate': pathlib.Path('source.py').write_text('changed while testing')\n"
        "print('1 failed' if mode == 'failed' else '1 passed in 0.01s')\n"
        "sys.exit(1 if mode == 'failed' else 0)\n"
    )
    runner.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("TEST_CALLS", str(tmp_path / "calls"))
    return session_store.register(root, "codex", "session")


def calls() -> list[dict]:
    path = Path(os.environ["TEST_CALLS"])
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_read_only_stop_does_not_test_preexisting_branch_changes(run: session_store.Run) -> None:
    assert "no changes" in gate.stop(run)["systemMessage"]
    assert calls() == []


def test_first_stop_after_edit_tests_registered_worktree_and_reuses_success(
    run: session_store.Run,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (run.root / "source.py").write_text("task edit")
    monkeypatch.chdir(tmp_path)
    assert "passed" in gate.stop(run)["systemMessage"]
    assert "reused" in gate.stop(run)["systemMessage"]
    assert len(calls()) == 1
    assert calls()[0]["cwd"] == str(run.root)
    assert calls()[0]["argv"][-1] == "tests/test_source.py"


def test_unchanged_failure_remains_unresolved_without_rerun_or_stop_loop(
    run: session_store.Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (run.root / "source.py").write_text("task edit")
    monkeypatch.setenv("TEST_OUTCOME", "failed")
    first = gate.stop(run)
    assert first["decision"] == "block"
    assert "failed" in first["reason"]
    repeated = gate.stop(run)
    assert "decision" not in repeated
    assert "unresolved" in repeated["systemMessage"]
    assert len(calls()) == 1
    assert next(iter(run.results()["checks"].values()))["status"] == "failed"


@pytest.mark.parametrize("source", ["startup", "resume", "compact"])
def test_session_start_reuses_failed_evidence_without_resetting_baseline(
    run: session_store.Run, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    (run.root / "source.py").write_text("task edit")
    monkeypatch.setenv("TEST_OUTCOME", "failed")
    assert gate.stop(run)["decision"] == "block"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(REPO_ROOT / "agents/hooks/verification_session.py"),
            "codex",
            "session-start",
        ],
        input=json.dumps({"cwd": str(run.root), "session_id": "session", "source": source}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {}
    assert "unresolved" in gate.stop(run)["systemMessage"]
    assert len(calls()) == 1


def test_edit_after_failure_is_rechecked_and_recovery_replaces_failure(
    run: session_store.Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (run.root / "source.py").write_text("bad edit")
    monkeypatch.setenv("TEST_OUTCOME", "failed")
    gate.stop(run)
    monkeypatch.setenv("TEST_OUTCOME", "passed")
    (run.root / "source.py").write_text("fixed")
    assert "passed" in gate.stop(run)["systemMessage"]
    assert len(calls()) == 2
    assert {value["status"] for value in run.results()["checks"].values()} == {"passed"}


def test_forced_retry_can_resolve_unchanged_external_failure(
    run: session_store.Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (run.root / "source.py").write_text("task edit")
    monkeypatch.setenv("TEST_OUTCOME", "failed")
    gate.stop(run)
    monkeypatch.setenv("TEST_OUTCOME", "passed")
    assert "passed" in gate.stop(run, force=True)["systemMessage"]
    assert len(calls()) == 2


def test_changes_during_tests_cannot_be_saved_as_current_success(
    run: session_store.Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (run.root / "source.py").write_text("task edit")
    monkeypatch.setenv("TEST_OUTCOME", "mutate")
    result = gate.stop(run)
    assert result["decision"] == "block"
    assert "changed during" in result["reason"]
    assert not run.results()["checks"]


def test_expired_resume_runs_tests_even_without_a_new_edit(run: session_store.Run) -> None:
    run.save_results({"checks": {}, "revalidate_all": True})
    assert "passed" in gate.stop(run)["systemMessage"]
    assert len(calls()) == 1


def test_timeout_remains_unresolved_without_repeating_the_same_wait(
    run: session_store.Run,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = tmp_path / "bin/uv"
    binary.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    monkeypatch.setenv("RUN_RELATED_TESTS_TIMEOUT_SECONDS", "0.1")
    (run.root / "source.py").write_text("task edit")
    assert "timeout" in gate.stop(run)["reason"]
    assert "unresolved" in gate.stop(run)["systemMessage"]


def test_skipped_only_tests_are_not_success(run: session_store.Run, tmp_path: Path) -> None:
    binary = tmp_path / "bin/uv"
    binary.write_text(f"#!{sys.executable}\nprint('1 skipped in 0.01s')\n")
    (run.root / "source.py").write_text("task edit")
    assert gate.stop(run)["decision"] == "block"


def test_relevant_configuration_changes_invalidate_receipts(run: session_store.Run) -> None:
    (run.root / "source.py").write_text("task edit")
    gate.stop(run)
    (run.root / "pyproject.toml").write_text("# changed test configuration")
    gate.stop(run)
    assert len(calls()) == 2


def test_log_budget_is_enforced_before_a_long_session_ends(
    run: session_store.Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_store, "TOTAL_LOG_LIMIT_BYTES", 1)
    monkeypatch.setenv("TEST_OUTCOME", "failed")
    (run.root / "source.py").write_text("task edit")
    assert gate.stop(run)["decision"] == "block"
    assert not list(run.directory.glob("logs/*.log"))
    assert "unresolved" in gate.stop(run)["systemMessage"]


def test_verbose_runner_output_does_not_inflate_reused_notifications(
    run: session_store.Run,
    tmp_path: Path,
) -> None:
    binary = tmp_path / "bin/uv"
    binary.write_text(f"#!{sys.executable}\nprint('1 passed ' + 'diagnostic ' * 20000)\n")
    (run.root / "source.py").write_text("task edit")
    for _ in range(2):
        notification = gate.stop(run)
        assert "passed" in notification["systemMessage"]
        assert len(json.dumps(notification)) < 4096
