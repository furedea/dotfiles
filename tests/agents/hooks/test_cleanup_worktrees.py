"""Merged task worktrees and branches are removed only when nothing unmerged would be lost."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT


SCRIPT = REPO_ROOT / "agents/hooks/cleanup_worktrees.py"


def git(*arguments: str, cwd: Path) -> str:
    return subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def primary(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git("init", "--quiet", "--initial-branch=main", cwd=root)
    git("config", "user.email", "test@example.com", cwd=root)
    git("config", "user.name", "Test", cwd=root)
    git("config", "commit.gpgsign", "false", cwd=root)
    (root / "README.md").write_text("base\n")
    git("add", "README.md", cwd=root)
    git("commit", "--quiet", "-m", "base", cwd=root)
    return root


@pytest.fixture
def merged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Fake gh and Herdr: merged PR heads come from this dict; Herdr records removals."""
    directory = tmp_path / "bin"
    directory.mkdir()
    state = tmp_path / "merged.json"
    removed = tmp_path / "herdr_removed.txt"
    (directory / "gh").write_text(f"#!/bin/sh\ncat {state}\n")
    listing = tmp_path / "herdr_worktrees.json"
    listing.write_text('{"result":{"worktrees":[]}}')
    (directory / "herdr").write_text(
        "#!/bin/sh\n"
        f'if [ "$2" = list ]; then cat {listing}; exit 0; fi\n'
        f'echo "$@" >> {removed}\n'
        f'git worktree remove "$(cat {tmp_path / "herdr_path.txt"})"\n'
    )
    for name in ("gh", "herdr"):
        (directory / name).chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")

    class Heads(dict):
        def __setitem__(self, branch: str, oid: str) -> None:
            super().__setitem__(branch, oid)
            state.write_text(json.dumps([{"headRefName": b, "headRefOid": o} for b, o in self.items()]))

    heads = Heads()
    state.write_text("[]")
    return heads


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


def test_a_merged_clean_worktree_and_its_branch_are_removed(primary: Path, merged: dict[str, str]) -> None:
    path = task_worktree(primary, "feat/done")
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=path)
    assert cleanup(primary).returncode == 0
    assert not path.exists()
    assert branches(primary) == {"main"}


def test_a_merged_branch_without_a_worktree_is_removed(primary: Path, merged: dict[str, str]) -> None:
    git("switch", "--quiet", "-c", "fix/old", cwd=primary)
    (primary / "old.txt").write_text("old\n")
    git("add", "old.txt", cwd=primary)
    git("commit", "--quiet", "-m", "old", cwd=primary)
    merged["fix/old"] = git("rev-parse", "HEAD", cwd=primary)
    git("switch", "--quiet", "main", cwd=primary)
    cleanup(primary)
    assert branches(primary) == {"main"}


@pytest.mark.parametrize("change", ["later commit", "dirty tree", "open pull request"])
def test_work_a_merge_does_not_cover_is_kept(primary: Path, merged: dict[str, str], change: str) -> None:
    path = task_worktree(primary, "feat/busy")
    if change != "open pull request":
        merged["feat/busy"] = git("rev-parse", "HEAD", cwd=path)
    if change == "later commit":
        (path / "more.txt").write_text("more\n")
        git("add", "more.txt", cwd=path)
        git("commit", "--quiet", "-m", "more", cwd=path)
    if change == "dirty tree":
        (path / "README.md").write_text("edited\n")
    cleanup(primary)
    assert path.exists()
    assert "feat/busy" in branches(primary)


def test_the_primary_and_current_checkouts_are_never_removed(primary: Path, merged: dict[str, str]) -> None:
    path = task_worktree(primary, "feat/here")
    merged["feat/here"] = git("rev-parse", "HEAD", cwd=path)
    merged["main"] = git("rev-parse", "HEAD", cwd=primary)
    cleanup(path)
    assert path.exists()
    assert primary.exists()
    assert {"main", "feat/here"} <= branches(primary)


def test_dry_run_reports_without_removing(primary: Path, merged: dict[str, str]) -> None:
    path = task_worktree(primary, "feat/done")
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=path)
    result = cleanup(primary, "--dry-run")
    assert "feat/done" in result.stdout
    assert path.exists()


def test_the_session_start_hook_never_blocks_the_session(primary: Path, merged: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(SCRIPT), "session-start"],
        input=json.dumps({"cwd": str(primary / "missing")}),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0


def test_an_open_herdr_workspace_is_closed_with_its_worktree(
    primary: Path, merged: dict[str, str], tmp_path: Path
) -> None:
    path = task_worktree(primary, "feat/lane")
    merged["feat/lane"] = git("rev-parse", "HEAD", cwd=path)
    (tmp_path / "herdr_path.txt").write_text(str(path))
    (tmp_path / "herdr_worktrees.json").write_text(
        json.dumps({"result": {"worktrees": [{"path": str(path), "open_workspace_id": "w9"}]}})
    )
    cleanup(primary)
    assert (tmp_path / "herdr_removed.txt").read_text().split() == ["worktree", "remove", "--workspace", "w9"]
    assert not path.exists()
    assert branches(primary) == {"main"}


def test_merged_herdr_lanes_of_other_repositories_are_swept_too(
    primary: Path, merged: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    lane = home / ".herdr/worktrees/repo/feat-elsewhere"
    lane.parent.mkdir(parents=True)
    git("worktree", "add", "--quiet", "-b", "feat/elsewhere", str(lane), cwd=primary)
    merged["feat/elsewhere"] = git("rev-parse", "HEAD", cwd=lane)
    monkeypatch.setenv("HOME", str(home))
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    assert cleanup(unrelated).returncode == 0
    assert not lane.exists()
    assert branches(primary) == {"main"}


def advance_origin(primary: Path, tmp_path: Path) -> str:
    """Give the primary an origin whose main is one squash-merge commit ahead, as after a merged PR."""
    origin = tmp_path / "origin.git"
    git("clone", "--quiet", "--bare", str(primary), str(origin), cwd=tmp_path)
    git("remote", "add", "origin", str(origin), cwd=primary)
    git("fetch", "--quiet", "origin", cwd=primary)
    git("branch", "--quiet", "--set-upstream-to=origin/main", "main", cwd=primary)
    upstream = tmp_path / "upstream"
    git("clone", "--quiet", str(origin), str(upstream), cwd=tmp_path)
    for key, value in (("user.email", "test@example.com"), ("user.name", "Test"), ("commit.gpgsign", "false")):
        git("config", key, value, cwd=upstream)
    (upstream / "merged.txt").write_text("merged\n")
    git("add", "merged.txt", cwd=upstream)
    git("commit", "--quiet", "-m", "squash merge", cwd=upstream)
    git("push", "--quiet", "origin", "main", cwd=upstream)
    return git("rev-parse", "HEAD", cwd=upstream)


def test_main_fast_forwards_after_a_merged_lane_is_removed(
    primary: Path, merged: dict[str, str], tmp_path: Path
) -> None:
    path = task_worktree(primary, "feat/done")
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=path)
    head = advance_origin(primary, tmp_path)
    cleanup(primary)
    assert git("rev-parse", "main", cwd=primary) == head
    assert (primary / "merged.txt").exists()


def test_main_advances_without_touching_another_checked_out_branch(
    primary: Path, merged: dict[str, str], tmp_path: Path
) -> None:
    path = task_worktree(primary, "feat/done")
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=path)
    head = advance_origin(primary, tmp_path)
    git("switch", "--quiet", "-c", "feat/mine", cwd=primary)
    cleanup(primary)
    assert git("rev-parse", "main", cwd=primary) == head
    assert git("branch", "--show-current", cwd=primary) == "feat/mine"
    assert not (primary / "merged.txt").exists()


@pytest.mark.parametrize("state", ["dirty main", "nothing removed"])
def test_main_stays_when_pulling_could_disturb_work_or_nothing_merged(
    primary: Path, merged: dict[str, str], tmp_path: Path, state: str
) -> None:
    if state == "dirty main":
        path = task_worktree(primary, "feat/done")
        merged["feat/done"] = git("rev-parse", "HEAD", cwd=path)
    before = git("rev-parse", "main", cwd=primary)
    advance_origin(primary, tmp_path)
    if state == "dirty main":
        (primary / "README.md").write_text("edited\n")
    cleanup(primary)
    assert git("rev-parse", "main", cwd=primary) == before
