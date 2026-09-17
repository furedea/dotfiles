"""Lint/format planning and notifications are independent of shell implementation details."""

import io
import json
from pathlib import Path
import subprocess

import pytest
from pytest_mock import MockerFixture

from tests.runtime import load_script_module


lint_format = load_script_module("agents/hooks/lint_format.py", "lint_format")


@pytest.mark.parametrize("marker", ["pyproject.toml", "uv.lock", "Cargo.toml"])
def test_nearest_project_marker_is_found_from_nested_directories(tmp_path: Path, marker: str) -> None:
    directory = tmp_path / "project"
    nested = directory / "src" / "package"
    nested.mkdir(parents=True)
    (directory / marker).touch()
    assert lint_format.project_root(nested, ("pyproject.toml", "uv.lock", "Cargo.toml")) == directory


def test_missing_project_marker_has_no_invented_root(tmp_path: Path) -> None:
    assert lint_format.project_root(tmp_path, ("nonexistent_marker_file.xyz",)) is None


@pytest.mark.parametrize(
    ("kind", "filename", "tools"),
    [
        ("sh", "file.sh", ("shfmt", "shellcheck")),
        ("js", "file.js", ("oxfmt", "oxlint", "oxlint")),
        ("json_toml", "file.json", ("dprint", "dprint")),
        ("rs", "file.rs", ("rustfmt",)),
        ("nix", "file.nix", ("nixfmt", "statix", "statix", "deadnix")),
        ("lua", "file.lua", ("stylua", "selene")),
        ("tex", "file.tex", ("tex-fmt", "chktex")),
        ("tex", "file.bib", ("tex-fmt",)),
        ("md", "file.md", ("autocorrect", "prettierd")),
        ("txt", "file.txt", ("autocorrect",)),
        ("gha", ".github/workflows/ci.yml", ("actionlint",)),
        ("gha", "other.yml", ()),
    ],
)
def test_language_plans_preserve_the_configured_quality_tools(
    tmp_path: Path, kind: str, filename: str, tools: tuple[str, ...]
) -> None:
    assert tuple(step.arguments[0] for step in lint_format.plan(kind, tmp_path / filename)) == tools


def test_python_project_uses_its_frozen_uv_tools(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").touch()
    steps = lint_format.plan("py", tmp_path / "src" / "file.py")
    assert all(step.arguments[:4] == ("uv", "run", "--frozen", "ruff") for step in steps)
    assert all(step.cwd == tmp_path for step in steps)
    assert [step.label for step in steps] == ["ruff format", "ruff fix", "ruff lint"]


def test_python_outside_a_project_uses_available_ruff(tmp_path: Path) -> None:
    assert all(step.arguments[0] == "ruff" for step in lint_format.plan("py", tmp_path / "file.py"))


def test_missing_tool_reports_target_and_prevents_later_steps(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(lint_format.shutil, "which", return_value=None, autospec=True)
    execute = mocker.patch.object(lint_format.subprocess, "run", autospec=True)
    target = tmp_path / "file with spaces.sh"
    assert lint_format.check_file("sh", target) == (
        f"Lint/format unavailable\nshfmt · {target}\nReason: shfmt not found in PATH.",
    )
    execute.assert_not_called()


def test_successful_steps_are_silent_even_with_output(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(
        lint_format.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"all good\n"), autospec=True
    )
    assert lint_format.run_step(lint_format.Step("example lint", ("example",)), tmp_path / "file") == ""


def test_failure_without_diagnostics_preserves_exit_status(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(
        lint_format.subprocess, "run", return_value=subprocess.CompletedProcess([], 3, b""), autospec=True
    )
    target = tmp_path / "source.sh"
    assert lint_format.run_step(lint_format.Step("example lint", ("example",)), target) == (
        f"Lint/format failed\nexample lint · {target} · exit 3\nError: No diagnostic output."
    )


def test_context_preserves_event_tool_label_and_multiline_diagnostics() -> None:
    message = "ruff lint: F401 unused import\nline2\nline3"
    assert json.loads(json.dumps(lint_format.context(message))) == {
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message},
    }


def test_missing_file_is_not_treated_as_a_successful_check(
    tmp_path: Path, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch.object(
        lint_format.sys, "stdin", io.StringIO(json.dumps({"tool_input": {"file_path": str(tmp_path / "missing")}}))
    )
    assert lint_format.main(["sh"]) == 1
    assert "File not found" in capsys.readouterr().err


def test_empty_input_does_not_execute_quality_tools(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]) -> None:
    mocker.patch.object(lint_format.sys, "stdin", io.StringIO('{"tool_input":{}}'))
    execute = mocker.patch.object(lint_format.subprocess, "run", autospec=True)
    assert lint_format.main(["sh"]) == 0
    execute.assert_not_called()
    assert capsys.readouterr().out == ""


def test_formatted_replacement_preserves_file_permissions(tmp_path: Path) -> None:
    target = tmp_path / "article.md"
    target.write_text("before")
    target.chmod(0o640)
    lint_format.replace_formatted_file(target, b"after")
    assert target.read_bytes() == b"after"
    assert target.stat().st_mode & 0o777 == 0o640
