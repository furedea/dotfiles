"""Config reload applies linked Herdr config to running servers without failing activation."""

import json
from pathlib import Path

import pytest

from tests.runtime import CliRunner, StubWriter


SCRIPT = "herdr/config_reload.py"
SESSIONS = {
    "sessions": [
        {"default": True, "name": "default", "running": False},
        {"default": False, "name": "main", "running": True},
        {"default": False, "name": "work", "running": True},
    ]
}
RUNNING = {"status": "running", "running": True, "compatible": True}
APPLIED = {
    "id": "cli:server:reload-config",
    "result": {"diagnostics": [], "status": "applied", "type": "config_reload"},
}


@pytest.fixture
def herdr(tmp_path: Path, executable: StubWriter, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERDR_FIXTURE", str(tmp_path))
    return executable(
        "herdr",
        """
        import json, os, sys
        from pathlib import Path
        args = sys.argv[1:]
        with (Path(os.environ["HERDR_FIXTURE"]) / "herdr.jsonl").open("a") as stream:
            stream.write(json.dumps(args) + "\\n")
        if args == ["session", "list", "--json"]:
            prefix = "HERDR_SESSIONS"
        elif args[:1] == ["--session"] and args[2:] == ["status", "server", "--json"]:
            prefix = "HERDR_STATUS"
        elif args[:1] == ["--session"] and args[2:] == ["server", "reload-config"]:
            prefix = "HERDR_RELOAD"
        else:
            sys.exit("unexpected herdr arguments: " + repr(args))
        print(os.environ.get(prefix + "_OUTPUT", ""))
        sys.exit(int(os.environ.get(prefix + "_EXIT_CODE", "0")))
    """,
    )


def reloaded_sessions(root: Path) -> list[str]:
    rows = [json.loads(line) for line in (root / "herdr.jsonl").read_text().splitlines()]
    return [row[1] for row in rows if row[2:] == ["server", "reload-config"]]


def outputs(sessions: object = SESSIONS, status: object = RUNNING, reload: object = APPLIED) -> dict[str, str]:
    return {
        "HERDR_SESSIONS_OUTPUT": json.dumps(sessions),
        "HERDR_STATUS_OUTPUT": json.dumps(status),
        "HERDR_RELOAD_OUTPUT": json.dumps(reload),
    }


def test_every_running_session_reloads_config_without_warning(run_cli: CliRunner, herdr: Path, tmp_path: Path) -> None:
    result = run_cli(SCRIPT, str(herdr), env=outputs())
    assert result.returncode == 0
    assert result.stderr == ""
    assert sorted(reloaded_sessions(tmp_path)) == ["main", "work"]


@pytest.mark.parametrize(
    "env",
    [
        pytest.param(outputs(sessions={"sessions": [SESSIONS["sessions"][0]]}), id="no-running-session"),
        pytest.param({"HERDR_SESSIONS_EXIT_CODE": "1"}, id="session-list-failed"),
        pytest.param({"HERDR_SESSIONS_OUTPUT": "not json"}, id="unreadable-session-list"),
        pytest.param(outputs(status={"status": "not_running", "running": False}), id="stopped"),
        pytest.param(outputs(status=RUNNING | {"compatible": False}), id="incompatible"),
        pytest.param(outputs() | {"HERDR_STATUS_EXIT_CODE": "1"}, id="status-failed"),
        pytest.param(outputs() | {"HERDR_STATUS_OUTPUT": "not json"}, id="unreadable-status"),
    ],
)
def test_unavailable_server_is_skipped_without_failing(
    run_cli: CliRunner, herdr: Path, tmp_path: Path, env: dict[str, str]
) -> None:
    result = run_cli(SCRIPT, str(herdr), env=env)
    assert result.returncode == 0
    assert reloaded_sessions(tmp_path) == []
    assert result.stdout + result.stderr != ""


def test_missing_herdr_executable_does_not_fail(run_cli: CliRunner, tmp_path: Path) -> None:
    result = run_cli(SCRIPT, str(tmp_path / "missing-herdr"))
    assert result.returncode == 0
    assert result.stdout + result.stderr != ""


@pytest.mark.parametrize(
    ("reload", "expected"),
    [
        pytest.param(
            {"result": {"diagnostics": [{"message": "unknown key 'prefx'"}], "status": "applied"}},
            "unknown key 'prefx'",
            id="diagnostics",
        ),
        pytest.param({"result": {"diagnostics": [], "status": "rejected"}}, "rejected", id="not-applied"),
    ],
)
def test_reload_problems_are_reported_as_warnings(
    run_cli: CliRunner, herdr: Path, reload: dict, expected: str
) -> None:
    result = run_cli(SCRIPT, str(herdr), env=outputs(reload=reload))
    assert result.returncode == 0
    assert "warning" in result.stderr.lower()
    assert expected in result.stderr


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({"HERDR_RELOAD_EXIT_CODE": "2", "HERDR_RELOAD_OUTPUT": "unrecognized subcommand"}, id="exit"),
        pytest.param({"HERDR_RELOAD_OUTPUT": "not json"}, id="unreadable"),
    ],
)
def test_failed_reload_warns_without_failing(run_cli: CliRunner, herdr: Path, env: dict[str, str]) -> None:
    result = run_cli(SCRIPT, str(herdr), env=outputs() | env)
    assert result.returncode == 0
    assert "warning" in result.stderr.lower()
