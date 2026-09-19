"""The lint/format CLI runs real tools and preserves process-level failures."""

import json
from pathlib import Path
import shutil

import pytest

from tests.runtime import CliRunner, StubWriter, load_script_module


lint_format = load_script_module("agents/hooks/lint_format.py", "lint_format")


def additional_context(output: str) -> str:
    rows = output.splitlines()
    assert len(rows) == 1
    context = json.loads(rows[0])["hookSpecificOutput"]
    assert context["hookEventName"] == "PostToolUse"
    return context["additionalContext"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "kind,source,expected,removed",
    [
        ("py", "x = 1\n", "x = 1\n", ""),
        ("py", "x=1\ny  =   2\n", "x = 1\ny = 2\n", ""),
        ("sh", '#!/bin/bash\nset -eo pipefail\necho "hello"\n', 'echo "hello"', ""),
        ("sh", '#!/bin/bash\nset -eo pipefail\nif true\nthen\necho "x"\nfi\n', "if true; then", ""),
        ("js", "const x = 1;\nconsole.log(x);\n", "const x = 1;", ""),
        ("js", "const   x=1\nconst y  =  2;\nconsole.log(x,y);\n", "const x = 1;", ""),
        ("rs", 'fn main(){let x=1;println!("{}",x);}\n', "fn main() {", ""),
    ],
)
def test_real_formatters_fix_files_without_residual_notifications(
    *, run_cli: CliRunner, tmp_path: Path, kind: str, source: str, expected: str, removed: str
) -> None:
    if kind == "rs" and not shutil.which("rustfmt"):
        pytest.skip("rustfmt not installed")
    if kind == "py":
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n[tool.ruff.format]\n")
    if kind == "js":
        (tmp_path / "package.json").write_text('{"devDependencies": {"oxfmt": "*"}}')
    path = tmp_path / f"source.{kind}"
    path.write_text(source)
    result = run_cli("agents/hooks/lint_format.py", kind, payload={"tool_input": {"file_path": str(path)}})
    assert result.returncode == 0
    assert "hookSpecificOutput" not in result.stdout
    assert expected in path.read_text()
    if removed:
        assert removed not in path.read_text()


@pytest.mark.integration
@pytest.mark.parametrize(
    "kind,source,diagnostic",
    [
        ("py", "def f():\n    return undefined_name\n", "F821"),
        ("sh", "#!/bin/bash\necho $1\n", "SC2086"),
        ("js", "var x = 1;\nvar x = 2;\n", ""),
    ],
)
def test_real_linter_residuals_reach_post_tool_context(
    run_cli: CliRunner, tmp_path: Path, kind: str, source: str, diagnostic: str
) -> None:
    path = tmp_path / f"source.{kind}"
    path.write_text(source)
    result = run_cli("agents/hooks/lint_format.py", kind, payload={"tool_input": {"file_path": str(path)}})
    assert result.returncode == 0
    assert diagnostic in additional_context(result.stdout)


@pytest.mark.parametrize("kind", ["gha", "js", "json_toml", "lua", "md", "nix", "py", "rs", "sh", "tex", "txt"])
def test_missing_file_events_are_quiet(run_cli: CliRunner, kind: str) -> None:
    result = run_cli("agents/hooks/lint_format.py", kind, payload={"tool_input": {}})
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("arguments,payload,diagnostic", [(["--help"], "", "Usage:"), (["py"], "{", "")])
def test_invalid_lint_format_invocations_fail(
    run_cli: CliRunner, arguments: list[str], payload: str, diagnostic: str
) -> None:
    result = run_cli("agents/hooks/lint_format.py", *arguments, payload=payload)
    assert result.returncode == 1
    assert diagnostic in result.stdout + result.stderr


@pytest.mark.parametrize(
    "kind,suffix,tool,phase",
    [
        ("sh", "sh", "shfmt", "format"),
        ("js", "js", "oxfmt", "format"),
        ("nix", "nix", "nixfmt", "format"),
        ("lua", "lua", "stylua", "format"),
        ("tex", "bib", "tex-fmt", "format"),
        ("txt", "txt", "autocorrect", "format"),
        ("md", "md", "prettierd", "format"),
        ("json_toml", "json", "dprint", "format"),
        ("sh", "sh", "shellcheck", "lint"),
        ("js", "js", "oxlint", "fix"),
        ("nix", "nix", "statix", "lint"),
        ("nix", "nix", "deadnix", "lint"),
        ("lua", "lua", "selene", "lint"),
        ("tex", "tex", "chktex", "lint"),
        ("json_toml", "toml", "dprint", "lint"),
        ("gha", "yml", "actionlint", "lint"),
    ],
)
def test_process_failures_survive_later_successful_steps(
    *, run_cli: CliRunner, executable: StubWriter, tmp_path: Path, kind: str, suffix: str, tool: str, phase: str
) -> None:
    for name in (
        "shfmt",
        "shellcheck",
        "oxfmt",
        "oxlint",
        "nixfmt",
        "statix",
        "deadnix",
        "stylua",
        "selene",
        "tex-fmt",
        "chktex",
        "autocorrect",
        "prettierd",
        "dprint",
        "actionlint",
    ):
        executable(
            name,
            """
            import os
            from pathlib import Path
            import sys
            if Path(sys.argv[0]).name == os.environ["FAILED_TOOL"]:
                print("formatter unavailable at runtime", file=sys.stderr)
                sys.exit(2)
        """,
        )
    if kind == "js":
        (tmp_path / "package.json").write_text('{"devDependencies": {"oxfmt": "*"}}')
    path = tmp_path / ".github/workflows" / f"source.{suffix}"
    path.parent.mkdir(parents=True)
    path.touch()
    result = run_cli(
        "agents/hooks/lint_format.py",
        kind,
        payload={"tool_input": {"file_path": str(path)}},
        env={"FAILED_TOOL": tool},
    )
    assert result.returncode == 0
    context = additional_context(result.stdout)
    assert "Lint/format failed" in context
    assert f"{tool} {phase} · {path} · exit 2" in context
    assert "Error: formatter unavailable at runtime" in context


@pytest.mark.parametrize(
    "kind,tool,message", [("py", "ruff", "formatter crashed"), ("rs", "rustfmt", "cannot parse source")]
)
def test_language_formatter_failure_is_not_hidden(
    *, run_cli: CliRunner, executable: StubWriter, tmp_path: Path, kind: str, tool: str, message: str
) -> None:
    executable(
        tool,
        f"""
        import sys
        if {kind!r} == "rs" or "format" in sys.argv:
            print({message!r}, file=sys.stderr)
            sys.exit(2)
    """,
    )
    if kind == "py":
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n[tool.ruff.format]\n")
    path = tmp_path / f"source.{kind}"
    path.touch()
    result = run_cli("agents/hooks/lint_format.py", kind, payload={"tool_input": {"file_path": str(path)}})
    assert result.returncode == 0
    context = additional_context(result.stdout)
    assert "failed" in context
    assert str(path) in context
    assert message in context


def test_multiple_diagnostics_are_one_valid_post_tool_output(
    run_cli: CliRunner, executable: StubWriter, tmp_path: Path
) -> None:
    executable(
        "ruff",
        """
        import sys
        print("F401 first")
        print("F821 second")
        sys.exit(1)
        """,
    )
    path = tmp_path / "source.py"
    path.touch()
    result = run_cli("agents/hooks/lint_format.py", "py", payload={"tool_input": {"file_path": str(path)}})
    assert result.returncode == 0
    row = json.loads(result.stdout)
    assert row["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "F401 first" in row["hookSpecificOutput"]["additionalContext"]
    assert "F821 second" in row["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("status", [0, 1])
def test_dprint_check_result_controls_notification(
    run_cli: CliRunner, executable: StubWriter, tmp_path: Path, status: int
) -> None:
    executable(
        "dprint",
        f"""
        import sys
        if sys.argv[1] == "check":
            if {status}:
                print("config.json is not formatted")
            sys.exit({status})
    """,
    )
    path = tmp_path / "config.json"
    path.write_text('{"ok":true}\n')
    result = run_cli("agents/hooks/lint_format.py", "json_toml", payload={"tool_input": {"file_path": str(path)}})
    assert result.returncode == 0
    if status:
        context = additional_context(result.stdout)
        assert "dprint" in context
        assert "config.json is not formatted" in context
    else:
        assert result.stdout == ""


def test_chktex_warning_is_visible_even_with_zero_exit(
    run_cli: CliRunner, executable: StubWriter, tmp_path: Path
) -> None:
    executable("tex-fmt", "")
    executable("chktex", 'print("Warning 1: unexpected spacing")\n')
    path = tmp_path / "source.tex"
    path.touch()
    result = run_cli("agents/hooks/lint_format.py", "tex", payload={"tool_input": {"file_path": str(path)}})
    assert result.returncode == 0
    context = additional_context(result.stdout)
    assert context == f"Lint/format failed\nchktex lint · {path} · exit 0\nDiagnostics: Warning 1: unexpected spacing"


def test_rust_file_formatting_does_not_run_project_wide_clippy(tmp_path: Path) -> None:
    assert all("clippy" not in step.arguments for step in lint_format.plan("rs", tmp_path / "source.rs"))
