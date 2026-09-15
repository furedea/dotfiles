"""Plugin synchronization preserves managed state across subprocess failures."""

import json
from pathlib import Path

import pytest

from conftest import CliRunner, StubWriter


SCRIPT = "herdr/plugin_sync.py"
PLUGIN = ("persiyanov.reviewr", "persiyanov/herdr-reviewr", "160ad607a195ee35ac9450e887974b3b5ddc4479")


@pytest.fixture
def plugin_remote(tmp_path: Path, executable: StubWriter, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PLUGIN_FIXTURE", str(tmp_path))
    monkeypatch.setenv("HERDR_PLUGIN_SYNC_STATE_FILE", str(tmp_path / "managed"))
    stub = executable(
        "herdr",
        """
        import json, os, sys
        from pathlib import Path
        root = Path(os.environ["PLUGIN_FIXTURE"])
        args = sys.argv[1:]
        with (root / "herdr.jsonl").open("a") as stream:
            stream.write(json.dumps(args) + "\\n")
        if args == ["plugin", "list", "--json"]:
            print(os.environ.get("HERDR_PLUGIN_LIST_JSON", '{"result":{"plugins":[]}}'))
        elif args[:2] == ["plugin", "install"]:
            status = int(os.environ.get("HERDR_INSTALL_EXIT_CODE", "0"))
            if status:
                print("plugin install failed", file=sys.stderr)
                sys.exit(status)
        elif args[:2] != ["plugin", "uninstall"]:
            sys.exit("unexpected herdr arguments: " + repr(args))
    """,
    )
    monkeypatch.setenv("HERDR_BIN", str(stub))
    return tmp_path


def installed(identifier: str, revision: str) -> dict[str, str]:
    return {
        "HERDR_PLUGIN_LIST_JSON": json.dumps(
            {"result": {"plugins": [{"plugin_id": identifier, "source": {"resolved_commit": revision}}]}}
        )
    }


def calls(root: Path) -> list[list[str]]:
    return [json.loads(line) for line in (root / "herdr.jsonl").read_text().splitlines()]


@pytest.mark.parametrize("present", [True, False])
def test_declared_revision_and_quiet_noop(run_cli: CliRunner, plugin_remote: Path, present: bool) -> None:
    result = run_cli(SCRIPT, *PLUGIN, env=installed(PLUGIN[0], PLUGIN[2]) if present else {})
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""
    assert (plugin_remote / "managed").read_text() == PLUGIN[0] + "\n"
    install = ["plugin", "install", PLUGIN[1], "--ref", PLUGIN[2], "--yes"]
    assert (install in calls(plugin_remote)) is not present


def test_removed_declaration_uninstalls_and_clears_state(run_cli: CliRunner, plugin_remote: Path) -> None:
    state = plugin_remote / "managed"
    state.write_text(PLUGIN[0] + "\n")
    result = run_cli(SCRIPT, env=installed(PLUGIN[0], PLUGIN[2]))
    assert result.returncode == 0
    assert ["plugin", "uninstall", PLUGIN[0]] in calls(plugin_remote)
    assert state.read_text() == ""


def test_failed_install_preserves_previous_state_and_plugins(run_cli: CliRunner, plugin_remote: Path) -> None:
    state = plugin_remote / "managed"
    state.write_text("existing.plugin\n")
    result = run_cli(
        SCRIPT,
        "new.plugin",
        "owner/new-plugin",
        "deadbeef",
        env=installed("existing.plugin", "cafebabe") | {"HERDR_INSTALL_EXIT_CODE": "17"},
    )
    assert result.returncode == 17
    assert state.read_text() == "existing.plugin\n"
    assert result.stderr == "plugin install failed\n"
    assert result.stdout == ""
    assert not any(row[:2] == ["plugin", "uninstall"] for row in calls(plugin_remote))
