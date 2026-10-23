"""Shared Git worktree setup and cleanup process helpers."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT

import cleanup_worktrees


SCRIPT = REPO_ROOT / "agents/hooks/cleanup_worktrees.py"


def git(*arguments: str, cwd: Path) -> str:
    return subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def task_worktree(primary: Path, branch: str) -> Path:
    path = primary.parent / branch.replace("/", "-")
    git("worktree", "add", "--quiet", "-b", branch, str(path), cwd=primary)
    (path / f"{branch.replace('/', '-')}.txt").write_text("work\n")
    git("add", ".", cwd=path)
    git("commit", "--quiet", "-m", branch, cwd=path)
    return path


def cleanup(cwd: Path, *arguments: str, payload: dict | None = None) -> subprocess.CompletedProcess[str]:
    """Exercise cleanup with a trusted primary regardless of the pytest temporary directory."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    with pytest.MonkeyPatch.context() as patch, redirect_stdout(stdout), redirect_stderr(stderr):
        patch.chdir(cwd)
        if payload is not None:
            patch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        returncode = cleanup_worktrees.main(list(arguments))
    return subprocess.CompletedProcess(arguments, returncode, stdout.getvalue(), stderr.getvalue())


def cleanup_with_real_policy(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-B", str(SCRIPT), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def branches(primary: Path) -> set[str]:
    return set(git("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=primary).splitlines())
