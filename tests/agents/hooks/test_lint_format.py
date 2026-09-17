"""Lint/format planning and notifications are independent of shell implementation details."""

import io
import json
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from tests.runtime import StubWriter, load_script_module


from lib import formatter_policy, lint_engine, process_runner


lint_format = load_script_module("agents/hooks/lint_format.py", "lint_format")


@pytest.mark.parametrize("marker", ["pyproject.toml", "uv.lock", "Cargo.toml"])
def test_nearest_project_marker_is_found_from_nested_directories(tmp_path: Path, marker: str) -> None:
    directory = tmp_path / "project"
    nested = directory / "src" / "package"
    nested.mkdir(parents=True)
    (directory / marker).touch()
    assert formatter_policy.project_root(nested, ("pyproject.toml", "uv.lock", "Cargo.toml")) == directory


def test_missing_project_marker_has_no_invented_root(tmp_path: Path) -> None:
    assert formatter_policy.project_root(tmp_path, ("nonexistent_marker_file.xyz",)) is None


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
    assert tuple(step.arguments[0] for step in formatter_policy.plan(kind, tmp_path / filename)) == tools


def test_python_project_uses_its_frozen_uv_tools(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
    steps = formatter_policy.plan("py", tmp_path / "src" / "file.py")
    assert all(step.arguments[:4] == ("uv", "run", "--frozen", "ruff") for step in steps)
    assert all(step.cwd == tmp_path for step in steps)
    assert [step.label for step in steps] == ["ruff format", "ruff fix", "ruff lint"]


def test_python_project_does_not_fallback_to_personal_ruff(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.black]\nline-length = 100\n")
    steps = formatter_policy.plan("py", tmp_path / "src" / "file.py")
    assert len(steps) == 1
    assert steps[0].policy_error is not None
    assert "black" in steps[0].policy_error
    assert steps[0].arguments == ()


def test_conflicting_python_formatters_are_not_guessed(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n[tool.black]\n")
    steps = formatter_policy.plan("py", tmp_path / "src" / "file.py")
    assert len(steps) == 1
    assert steps[0].policy_error is not None
    assert "multiple formatters" in steps[0].policy_error


def test_project_formatter_policy_is_reported_without_running_a_tool(tmp_path: Path, mocker: MockerFixture) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.black]\n")
    target = tmp_path / "source.py"
    target.touch()
    which = mocker.patch.object(lint_engine.shutil, "which", autospec=True)
    messages = lint_engine.check_file("py", target)
    assert len(messages) == 1
    assert "black" in messages[0]
    which.assert_not_called()


def test_python_outside_a_project_uses_available_ruff(tmp_path: Path) -> None:
    assert all(step.arguments[0] == "ruff" for step in formatter_policy.plan("py", tmp_path / "file.py"))


def test_dprint_project_config_takes_precedence_over_personal_config(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = project / "dprint.json"
    config.write_text("{}")
    target = project / "src" / "config.json"
    target.parent.mkdir()
    steps = formatter_policy.plan("json_toml", target)
    assert all(step.arguments[0] == "dprint" for step in steps)
    assert all(str(config) in step.arguments for step in steps)
    assert all(step.cwd == project for step in steps)


def test_personal_dprint_runs_from_the_target_directory(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    steps = formatter_policy.plan("json_toml", target)
    assert all(step.cwd == tmp_path for step in steps)
    assert all(str(Path.home() / "dprint.json") in step.arguments for step in steps)


def test_other_project_formatter_prevents_personal_dprint_fallback(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".prettierrc").write_text("{}")
    steps = formatter_policy.plan("json_toml", project / "config.json")
    assert len(steps) == 1
    assert steps[0].policy_error is not None
    assert "prettier" in steps[0].policy_error
    assert steps[0].arguments == ()


def test_conflicting_project_formatters_are_not_guessed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "dprint.json").write_text("{}")
    (project / ".prettierrc").write_text("{}")
    steps = formatter_policy.plan("json_toml", project / "config.json")
    assert len(steps) == 1
    assert steps[0].policy_error is not None
    assert "conflict" in steps[0].policy_error


def test_missing_tool_reports_target_and_prevents_later_steps(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(lint_engine.shutil, "which", return_value=None, autospec=True)
    execute = mocker.patch.object(process_runner, "run_process", autospec=True)
    target = tmp_path / "file with spaces.sh"
    assert lint_engine.check_file("sh", target) == (
        f"Lint/format unavailable\nshfmt · {target}\nReason: shfmt not found in PATH.",
    )
    execute.assert_not_called()


def test_successful_steps_are_silent_even_with_output(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(
        process_runner,
        "run_process",
        return_value=process_runner.ProcessResult(0, diagnostics=b"all good\n"),
        autospec=True,
    )
    assert lint_engine.run_step(formatter_policy.Step("example lint", ("example",)), tmp_path / "file") == ""


def test_process_output_is_bounded(executable: StubWriter, tmp_path: Path) -> None:
    executable("noisy", "import sys; print('diagnostic ' * 100000); sys.exit(1)")
    message = lint_engine.run_step(formatter_policy.Step("example lint", ("noisy",)), tmp_path / "file")
    assert len(message.encode()) < process_runner.PROCESS_OUTPUT_LIMIT_BYTES + 256
    assert "[process output truncated]" in message


def test_process_timeout_is_reported(executable: StubWriter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable("slow", "import time; time.sleep(1)")
    monkeypatch.setattr(process_runner, "STEP_TIMEOUT_SECONDS", 0.01)
    message = lint_engine.run_step(formatter_policy.Step("example lint", ("slow",)), tmp_path / "file")
    assert "Lint/format timeout" in message
    assert "0.01s" in message


def test_formatted_output_limit_does_not_replace_the_target(executable: StubWriter, tmp_path: Path) -> None:
    executable("formatted", "import sys; sys.stdout.write('x' * 10000000)")
    target = tmp_path / "article.md"
    target.write_bytes(b"before")
    message = lint_engine.run_step(formatter_policy.Step("formatted", ("formatted",), writes_stdout=True), target)
    assert "Formatted output exceeded" in message
    assert target.read_bytes() == b"before"


def test_formatter_diagnostics_are_bounded_separately_from_formatted_output(
    executable: StubWriter, tmp_path: Path
) -> None:
    executable("formatted-warning", "import sys; sys.stdout.write('after'); sys.stderr.write('warning ' * 100000)")
    target = tmp_path / "article.md"
    target.write_bytes(b"before")
    message = lint_engine.run_step(
        formatter_policy.Step("formatted", ("formatted-warning",), writes_stdout=True, reports_warnings=True), target
    )
    assert "[process output truncated]" in message
    assert target.read_bytes() == b"after"


def test_failure_without_diagnostics_preserves_exit_status(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(process_runner, "run_process", return_value=process_runner.ProcessResult(3), autospec=True)
    target = tmp_path / "source.sh"
    assert lint_engine.run_step(formatter_policy.Step("example lint", ("example",)), target) == (
        f"Lint/format failed\nexample lint · {target} · exit 3\nError: No diagnostic output."
    )


def test_context_preserves_event_tool_label_and_multiline_diagnostics() -> None:
    message = "ruff lint: F401 unused import\nline2\nline3"
    assert json.loads(json.dumps(lint_format.context(message))) == {
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message},
    }


def test_provider_diagnostics_are_bounded_without_losing_truncation_notice(
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = tuple(f"diagnostic {index}: {'x' * 2000}" for index in range(20))
    lint_format.emit(messages)
    output = capsys.readouterr().out
    row = json.loads(output)
    context = row["hookSpecificOutput"]["additionalContext"]
    assert len(context.encode()) <= lint_format.NOTIFICATION_LIMIT_BYTES
    assert "[diagnostics truncated]" in context
    assert "diagnostic 0" in context


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
    execute = mocker.patch.object(lint_format, "run_process", autospec=True)
    assert lint_format.main(["sh"]) == 0
    execute.assert_not_called()
    assert capsys.readouterr().out == ""


def test_dispatcher_selects_files_from_a_codex_patch_and_deduplicates(tmp_path: Path, mocker: MockerFixture) -> None:
    first = tmp_path / "src" / "one.py"
    second = tmp_path / "src" / "two.sh"
    first.parent.mkdir()
    first.touch()
    second.touch()
    check = mocker.patch.object(lint_format, "check_file", return_value=())
    payload = {
        "cwd": str(tmp_path),
        "tool_name": "apply_patch",
        "tool_input": {
            "command": "*** Begin Patch\n*** Update File: src/one.py\n*** Update File: src/one.py\n"
            "*** Update File: src/two.sh\n*** Update File: src/missing.py\n*** End Patch"
        },
    }

    assert lint_format.diagnostics(payload) == ()
    assert check.call_args_list == [mocker.call("py", first), mocker.call("sh", second)]


def test_dispatcher_uses_only_the_file_tool_path(tmp_path: Path, mocker: MockerFixture) -> None:
    path = tmp_path / "source.py"
    path.touch()
    check = mocker.patch.object(lint_format, "check_file", return_value=())

    assert (
        lint_format.diagnostics({"tool_name": "Write", "tool_input": {"file_path": str(path), "content": "secret"}})
        == ()
    )
    check.assert_called_once_with("py", path)


def test_dispatcher_skips_unsupported_files(tmp_path: Path, mocker: MockerFixture) -> None:
    path = tmp_path / "archive.bin"
    path.touch()
    check = mocker.patch.object(lint_format, "check_file", return_value=())

    assert lint_format.diagnostics({"tool_name": "Write", "tool_input": {"file_path": str(path)}}) == ()
    check.assert_not_called()


def test_formatted_replacement_preserves_file_permissions(tmp_path: Path) -> None:
    target = tmp_path / "article.md"
    target.write_text("before")
    target.chmod(0o640)
    lint_engine.replace_formatted_file(target, b"after")
    assert target.read_bytes() == b"after"
    assert target.stat().st_mode & 0o777 == 0o640
