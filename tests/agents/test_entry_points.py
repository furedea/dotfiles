"""Source entry points that providers execute directly are runnable scripts."""

import os
import subprocess

import pytest

from tests.runtime import REPO_ROOT


ENTRY_POINTS = (
    "agents/codex/hooks/hook_adapter.py",
    "agents/devin/hooks/hook_adapter.py",
    "agents/hermes/hooks/hook_adapter.py",
    "agents/pi/hooks/hook_adapter.py",
    "agents/claude/statusline/statusline.py",
)


@pytest.mark.parametrize("name", ENTRY_POINTS)
def test_entry_point_is_an_executable_script(name: str) -> None:
    path = REPO_ROOT / name
    assert os.access(path, os.X_OK), name
    assert path.read_text().startswith("#!/usr/bin/env -S python3"), name


@pytest.mark.parametrize("name", ENTRY_POINTS)
def test_entry_point_is_executable_in_the_git_index(name: str) -> None:
    # Nix builds the rendered harness from the Git tree, so the index mode is what ships.
    result = subprocess.run(
        ["git", "ls-files", "--stage", "--", name], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    assert result.stdout.startswith("100755 "), result.stdout or name
