"""Config reload applies linked Herdr config to a running server without failing activation."""

import json
from pathlib import Path

import pytest

from tests.runtime import CliRunner, StubWriter


SCRIPT = "herdr/config_reload.py"
RUNNING = {"status": "running", "running": True, "compatible": True, "session": "main"}
APPLIED = {
    "id": "cli:server:reload-config",
    "result": {"diagnostics": [], "status": "applied", "type": "config_reload"},
}
RELOAD = ["server", "reload-config"]


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
        if args == ["status", "server", "--json"]:
            prefix = "HERDR_STATUS"
        elif args == ["server", "reload-config"]:
            prefix = "HERDR_RELOAD"
        else:
            sys.exit("unexpected herdr arguments: " + repr(args))
        print(os.environ.get(prefix + "_OUTPUT", ""))
        sys.exit(int(os.environ.get(prefix + "_EXIT_CODE", "0")))
    """,
    )


def calls(root: Path) -> list[list[str]]:
    return [json.loads(line) for line in (root / "herdr.jsonl").read_text().splitlines()]


def outputs(status: object, reload: object = APPLIED) -> dict[str, str]:
    return {"HERDR_STATUS_OUTPUT": json.dumps(status), "HERDR_RELOAD_OUTPUT": json.dumps(reload)}


def test_running_server_reloads_config_without_warning(run_cli: CliRunner, herdr: Path, tmp_path: Path) -> None:
    result = run_cli(SCRIPT, str(herdr), env=outputs(RUNNING))
    assert result.returncode == 0
    assert result.stderr == ""
    assert RELOAD in calls(tmp_path)


@pytest.mark.parametrize(
    "env",
    [
        pytest.param(outputs({"status": "not_running", "running": False}), id="stopped"),
        pytest.param(outputs(RUNNING | {"compatible": False}), id="incompatible"),
        pytest.param({"HERDR_STATUS_EXIT_CODE": "1"}, id="status-failed"),
        pytest.param({"HERDR_STATUS_OUTPUT": "not json"}, id="unreadable-status"),
    ],
)
def test_unavailable_server_is_skipped_without_failing(
    run_cli: CliRunner, herdr: Path, tmp_path: Path, env: dict[str, str]
) -> None:
    result = run_cli(SCRIPT, str(herdr), env=env)
    assert result.returncode == 0
    assert RELOAD not in calls(tmp_path)
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
    result = run_cli(SCRIPT, str(herdr), env=outputs(RUNNING, reload))
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
    result = run_cli(SCRIPT, str(herdr), env={"HERDR_STATUS_OUTPUT": json.dumps(RUNNING)} | env)
    assert result.returncode == 0
    assert "warning" in result.stderr.lower()
