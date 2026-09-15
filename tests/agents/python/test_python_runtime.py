"""Direct executable entry points retain deployment and import-isolation contracts."""

import json
import os
from pathlib import Path
import subprocess

import pytest

from conftest import HarnessRunner, REPO_ROOT


@pytest.mark.integration
def test_rendered_hooks_load_adjacent_modules(agent_harness: HarnessRunner, isolated_project: Path) -> None:
    prefix = isolated_project / "rendered"
    agent_harness("install", "--prefix", str(prefix), "--runtime-root", str(prefix))
    for name in (
        ".claude/hooks/guard_command.py",
        ".claude/hooks/lib/shell_syntax.py",
        ".codex/hooks/hook_translation.py",
        ".claude/statusline/statusline.py",
    ):
        assert (prefix / name).is_file(), name
    environment = os.environ | {"AGENT_HARNESS_ROOT": str(prefix)}
    for name in ("AGENT_COMMAND_PERMISSIONS", "AGENT_ALLOWED_COMMAND_RULES", "AGENT_FORBIDDEN_COMMAND_RULES"):
        environment.pop(name, None)
    executable = prefix / ".codex/hooks/hook_translation.py"
    for arguments, payload, status, message in (
        (["shell", "allowed"], {"tool_input": {"cmd": "git status"}}, 0, ""),
        (["paths", "patch"], {"tool_input": {"file_path": ".env.local"}}, 2, "secret path policy matched"),
    ):
        result = subprocess.run(
            [str(executable), *arguments],
            input=json.dumps(payload),
            env=environment,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == status, result.stderr
        assert message in result.stderr


def test_direct_entry_point_ignores_project_and_user_module_injection(tmp_path: Path) -> None:
    (tmp_path / "json.py").write_text('raise RuntimeError("untrusted json module")\n')
    (tmp_path / "sitecustomize.py").write_text('raise RuntimeError("untrusted user site")\n')
    result = subprocess.run(
        [str(REPO_ROOT / "github/repo.py"), "create", "--help"],
        cwd=tmp_path,
        env=os.environ | {"PYTHONPATH": str(tmp_path)},
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert "Usage:" in result.stderr
    assert "untrusted" not in result.stdout + result.stderr
