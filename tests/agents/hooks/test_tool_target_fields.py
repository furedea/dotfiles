"""NotebookEdit and Grep payload fields reach the shared file guards and lint targets."""

import json
from pathlib import Path

import pytest

from tests.runtime import CliRunner, load_script_module


SCRIPT = "agents/hooks/guard_file.py"
MARKER = "fixture-sensitive-marker"
hook_input = load_script_module("agents/hooks/lib/hook_input.py", "hook_input")
audit = load_script_module("agents/hooks/audit_log.py", "audit_log")


@pytest.fixture(autouse=True)
def policies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    protected = tmp_path / "protected.json"
    protected.write_text(json.dumps({"version": 1, "paths": ["~/.claude/settings.json"]}))
    patterns = tmp_path / "patterns.json"
    patterns.write_text(json.dumps({"fixture": {"pattern": MARKER, "message": "Fixture detected"}}))
    monkeypatch.setenv("AGENT_PROTECTED_PATH_POLICY", str(protected))
    monkeypatch.setenv("AGENT_SECRET_CONTENT_PATTERNS", str(patterns))


def notebook_edit(path: str, source: str = "x = 1") -> dict:
    return {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": path, "new_source": source}}


def test_notebook_edit_on_a_harness_file_is_blocked(run_cli: CliRunner) -> None:
    result = run_cli(SCRIPT, "harness", payload=notebook_edit("~/.claude/settings.json"))
    assert result.returncode == 2
    assert "agent harness boundary" in result.stderr


@pytest.mark.parametrize("source,blocked", [(MARKER, True), ("x = 1", False)])
def test_notebook_edit_source_is_scanned(run_cli: CliRunner, source: str, blocked: bool) -> None:
    result = run_cli(SCRIPT, "write", payload=notebook_edit("analysis.ipynb", source))
    assert result.returncode == 0
    if blocked:
        assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    else:
        assert result.stdout == ""


@pytest.mark.parametrize("target,blocked", [("secret.txt", True), (".", False)])
def test_grep_scans_a_single_file_target_only(
    run_cli: CliRunner, isolated_project: Path, target: str, blocked: bool
) -> None:
    (isolated_project / "secret.txt").write_text(MARKER + "\n")
    payload = {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": str(isolated_project / target)}}
    result = run_cli(SCRIPT, "read", payload=payload)
    assert result.returncode == 0
    if blocked:
        assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    else:
        assert result.stdout == ""


def test_notebook_edit_target_reaches_lint(tmp_path: Path) -> None:
    payload = notebook_edit("analysis.ipynb") | {"cwd": str(tmp_path)}
    assert hook_input.target_paths(payload) == (tmp_path.resolve() / "analysis.ipynb",)


def test_notebook_edit_target_is_audited(tmp_path: Path) -> None:
    entry = audit.record("tool", notebook_edit("analysis.ipynb") | {"cwd": str(tmp_path)})
    assert entry is not None
    assert entry["targets"] == ["analysis.ipynb"]
