"""Shared Git worktree setup and cleanup process helpers."""

from pathlib import Path
import subprocess
import sys

from tests.runtime import REPO_ROOT


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


def cleanup(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
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
