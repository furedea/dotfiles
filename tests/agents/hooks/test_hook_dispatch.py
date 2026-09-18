"""Manifest fan-out executes configured commands and propagates their decisions."""

import json
from pathlib import Path
import sys

import pytest

from tests.runtime import REPO_ROOT, StubWriter


sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
import hook_dispatch


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    return tmp_path / "hooks.json"


def write_manifest(path: Path, event: str, groups: list[dict]) -> None:
    path.write_text(json.dumps({"hooks": {event: groups}}))


def called_marker(tmp_path: Path) -> tuple[str, Path]:
    marker = tmp_path / "called"
    source = f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n"
    return source, marker


def test_missing_manifest_is_a_noop(manifest: Path) -> None:
    assert hook_dispatch.run(manifest, "pre_tool_call", {"tool_name": "bash"}) == 0


def test_event_without_groups_is_a_noop(manifest: Path) -> None:
    write_manifest(manifest, "pre_tool_call", [])
    assert hook_dispatch.run(manifest, "other_event", {"tool_name": "bash"}) == 0


def test_runs_matching_commands_with_the_payload_on_stdin(
    manifest: Path, executable: StubWriter, tmp_path: Path
) -> None:
    seen = tmp_path / "seen.json"
    stub = executable(
        "record-payload",
        f"""
        import sys
        from pathlib import Path
        Path({str(seen)!r}).write_text(sys.stdin.read())
        """,
    )
    write_manifest(
        manifest,
        "pre_tool_call",
        [{"matcher": "^bash$", "hooks": [{"command": str(stub), "type": "command"}]}],
    )
    payload = {"tool_name": "bash", "tool_input": {"command": "ls"}}

    assert hook_dispatch.run(manifest, "pre_tool_call", payload) == 0
    assert json.loads(seen.read_text()) == payload


def test_matcher_skips_non_matching_tools(manifest: Path, executable: StubWriter, tmp_path: Path) -> None:
    source, marker = called_marker(tmp_path)
    stub = executable("mark-called", source)
    write_manifest(
        manifest,
        "pre_tool_call",
        [{"matcher": "^bash$", "hooks": [{"command": str(stub), "type": "command"}]}],
    )

    assert hook_dispatch.run(manifest, "pre_tool_call", {"tool_name": "read"}) == 0
    assert not marker.exists()


def test_absent_matcher_matches_every_payload(manifest: Path, executable: StubWriter, tmp_path: Path) -> None:
    source, marker = called_marker(tmp_path)
    stub = executable("mark-called", source)
    write_manifest(
        manifest,
        "on_session_start",
        [{"hooks": [{"command": str(stub), "type": "command"}]}],
    )

    assert hook_dispatch.run(manifest, "on_session_start", {}) == 0
    assert marker.exists()


def test_exit_code_two_propagates_with_stderr(
    manifest: Path, executable: StubWriter, capsys: pytest.CaptureFixture
) -> None:
    stub = executable(
        "block-hard",
        """
        import sys
        print("forbidden command", file=sys.stderr)
        sys.exit(2)
        """,
    )
    write_manifest(
        manifest,
        "pre_tool_call",
        [{"hooks": [{"command": str(stub), "type": "command"}]}],
    )

    assert hook_dispatch.run(manifest, "pre_tool_call", {}) == 2
    assert "forbidden command" in capsys.readouterr().err


@pytest.mark.parametrize(
    "output",
    [
        {"decision": "block", "reason": "policy says no"},
        {"action": "block", "message": "policy says no"},
        {"action": "approve", "message": "needs review"},
    ],
)
def test_decision_output_is_reemitted(
    manifest: Path, executable: StubWriter, capsys: pytest.CaptureFixture, output: dict
) -> None:
    stub = executable(
        "emit-decision",
        f"""
        import json
        print(json.dumps({output!r}))
        """,
    )
    write_manifest(
        manifest,
        "pre_tool_call",
        [{"hooks": [{"command": str(stub), "type": "command"}]}],
    )

    assert hook_dispatch.run(manifest, "pre_tool_call", {}) == 0
    assert json.loads(capsys.readouterr().out.strip()) == output


def test_nonzero_exit_other_than_two_is_ignored(manifest: Path, executable: StubWriter) -> None:
    stub = executable(
        "fail-soft",
        """
        import sys
        print("oops", file=sys.stderr)
        sys.exit(1)
        """,
    )
    write_manifest(
        manifest,
        "pre_tool_call",
        [{"hooks": [{"command": str(stub), "type": "command"}]}],
    )

    assert hook_dispatch.run(manifest, "pre_tool_call", {}) == 0


def test_environment_variables_expand_in_commands(
    manifest: Path, executable: StubWriter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, marker = called_marker(tmp_path)
    stub = executable("mark-called", source)
    monkeypatch.setenv("STUB_DIR", str(stub.parent))
    write_manifest(
        manifest,
        "pre_tool_call",
        [{"hooks": [{"command": "$STUB_DIR/mark-called", "type": "command"}]}],
    )

    assert hook_dispatch.run(manifest, "pre_tool_call", {}) == 0
    assert marker.exists()


def test_first_decision_wins_but_remaining_hooks_still_observe(
    manifest: Path, executable: StubWriter, capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    stub = executable(
        "emit-decision",
        """
        import json
        print(json.dumps({"decision": "block", "reason": "first"}))
        """,
    )
    source, marker = called_marker(tmp_path)
    second = executable("still-runs", source)
    write_manifest(
        manifest,
        "pre_tool_call",
        [
            {
                "hooks": [
                    {"command": str(stub), "type": "command"},
                    {"command": str(second), "type": "command"},
                ]
            }
        ],
    )

    assert hook_dispatch.run(manifest, "pre_tool_call", {}) == 0
    assert json.loads(capsys.readouterr().out.strip())["reason"] == "first"
    assert marker.exists()


def test_context_output_does_not_stop_later_hooks(
    manifest: Path, executable: StubWriter, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    stub = executable(
        "emit-context",
        """
        import json
        print(json.dumps({"hookSpecificOutput": {"additionalContext": "note"}}))
        """,
    )
    source, marker = called_marker(tmp_path)
    second = executable("still-runs", source)
    write_manifest(
        manifest,
        "on_session_start",
        [
            {
                "hooks": [
                    {"command": str(stub), "type": "command"},
                    {"command": str(second), "type": "command"},
                ]
            }
        ],
    )

    assert hook_dispatch.run(manifest, "on_session_start", {}) == 0
    assert capsys.readouterr().out == ""
    assert marker.exists()
