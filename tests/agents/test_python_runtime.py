"""Rendered agent entry points load their deployed dependencies."""

import json
import os
from pathlib import Path
import subprocess

import pytest

from tests.runtime import CliRunner


ADAPTERS = (".codex/hooks", ".devin/hooks", ".hermes/hooks", ".pi/hooks")


@pytest.fixture
def rendered(agent_harness: CliRunner, isolated_project: Path) -> Path:
    prefix = isolated_project / "rendered"
    agent_harness("install", "--prefix", str(prefix), "--runtime-root", str(prefix))
    return prefix


@pytest.fixture
def environment(rendered: Path) -> dict[str, str]:
    result = os.environ | {"AGENT_HARNESS_ROOT": str(rendered)}
    for name in ("AGENT_COMMAND_PERMISSIONS", "AGENT_ALLOWED_COMMAND_RULES", "AGENT_FORBIDDEN_COMMAND_RULES"):
        result.pop(name, None)
    return result


def run(
    executable: Path, arguments: list[str], payload: dict, environment: dict[str, str]
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(executable), *arguments],
        input=json.dumps(payload),
        env=environment,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


@pytest.mark.integration
def test_rendered_hooks_load_adjacent_modules(rendered: Path, environment: dict[str, str]) -> None:
    for name in (
        ".claude/hooks/guard_command.py",
        ".claude/hooks/lint_format.py",
        ".claude/hooks/lib/shell_syntax.py",
        ".claude/hooks/lib/provider_adapter.py",
        ".claude/statusline/statusline.py",
        *(f"{directory}/hook_adapter.py" for directory in ADAPTERS),
    ):
        assert (rendered / name).is_file(), name
    result = run(rendered / ".claude/hooks/lint_format.py", ["py"], {"tool_input": {}}, environment)
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


@pytest.mark.integration
@pytest.mark.parametrize("directory", ADAPTERS)
@pytest.mark.parametrize(
    "case",
    [
        (["shell", "allowed"], {"tool_input": {"cmd": "git status"}}, 0, ""),
        (["paths", "patch"], {"tool_input": {"file_path": ".env.local"}}, 2, "secret path policy matched"),
    ],
)
def test_rendered_provider_adapters_run_shared_guards(
    rendered: Path, environment: dict[str, str], directory: str, case: tuple[list[str], dict, int, str]
) -> None:
    arguments, payload, status, message = case
    result = run(rendered / directory / "hook_adapter.py", arguments, payload, environment)
    assert result.returncode == status, result.stderr
    assert message in result.stderr
