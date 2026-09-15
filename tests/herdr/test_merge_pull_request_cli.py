"""Merge confirmation and failure visibility at the actual stdin/process boundary."""

import json
from pathlib import Path

import pytest

from tests.runtime import CliRunner, StubWriter


SCRIPT = "herdr/merge_pull_request.py"
HEAD = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def merge_remote(tmp_path: Path, executable: StubWriter, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MERGE_FIXTURE", str(tmp_path))
    monkeypatch.setenv("GIT_HEAD", HEAD)
    gh = executable(
        "gh",
        """
        import json, os, sys
        from pathlib import Path
        root = Path(os.environ["MERGE_FIXTURE"])
        args = sys.argv[1:]
        with (root / "gh.jsonl").open("a") as stream:
            stream.write(json.dumps(args) + "\\n")
        assert args[:2] in (["pr", "view"], ["pr", "merge"])
        kind = "VIEW" if args[1] == "view" else "MERGE"
        status = int(os.environ.get(f"GH_{kind}_EXIT_CODE", "0"))
        if status:
            print(os.environ[f"GH_{kind}_ERROR"], file=sys.stderr)
            sys.exit(status)
        if kind == "VIEW":
            print("42\\tMerge helper\\tmain\\tfeature/test")
    """,
    )
    git = executable(
        "git",
        """
        import os, sys
        args = sys.argv[1:]
        root = os.environ["MERGE_FIXTURE"]
        tail = args[2:]
        kind = "ROOT" if tail == ["rev-parse", "--show-toplevel"] else "HEAD" if tail == ["rev-parse", "HEAD"] else ""
        status = int(os.environ.get(f"GIT_{kind}_EXIT_CODE", "0"))
        if status:
            print(os.environ[f"GIT_{kind}_ERROR"], file=sys.stderr)
            sys.exit(status)
        if kind == "ROOT":
            print(root)
        elif kind == "HEAD":
            print(os.environ["GIT_HEAD"])
        elif tail == ["status", "--porcelain=v1"]:
            print(os.environ.get("GIT_STATUS_OUTPUT", ""))
        elif tail == ["worktree", "list", "--porcelain"]:
            print(os.environ.get("GIT_WORKTREE_OUTPUT", f"worktree {root}\\nbranch refs/heads/feature/test\\n"))
        else:
            sys.exit("unexpected git arguments: " + repr(args))
    """,
    )
    monkeypatch.setenv("GH_BIN", str(gh))
    monkeypatch.setenv("GIT_BIN", str(git))
    return tmp_path


def gh_calls(root: Path) -> list[list[str]]:
    path = root / "gh.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.mark.parametrize(
    "key,confirm", [("\n", True), ("\r\n", True), ("\x1b\n", False), ("\x03\n", False), ("", False), ("x\n", False)]
)
def test_confirmation_keys(run_cli: CliRunner, merge_remote: Path, key: str, confirm: bool) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload=key)
    assert result.returncode == 0, result.stderr
    logged = gh_calls(merge_remote)
    if confirm:
        assert ["pr", "merge", "--squash", "--delete-branch", "--match-head-commit", HEAD] in logged
        assert not any("--auto" in row for row in logged)
    else:
        assert "Cancelled." in result.stdout
        assert not any(row[:2] == ["pr", "merge"] for row in logged)
    assert "PR #42: Merge helper" in result.stdout
    assert "feature/test -> main" in result.stdout
    assert "Enter / Ctrl+M  Squash and merge now" in result.stdout
    if key == "x\n":
        assert "Press Enter or Esc to close" in result.stdout


def test_dirty_tree_prevents_merge(run_cli: CliRunner, merge_remote: Path) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload="\n", env={"GIT_STATUS_OUTPUT": " M herdr/config.toml\n"})
    assert result.returncode == 1
    assert "working tree has uncommitted changes" in result.stdout
    assert not gh_calls(merge_remote)


def test_linked_base_preserves_local_branch(run_cli: CliRunner, merge_remote: Path) -> None:
    worktrees = f"worktree {merge_remote}\nbranch refs/heads/feature/test\n\nworktree {merge_remote}/elsewhere\nbranch refs/heads/main\n"
    result = run_cli(SCRIPT, str(merge_remote), payload="\n", env={"GIT_WORKTREE_OUTPUT": worktrees})
    assert result.returncode == 0
    assert ["pr", "merge", "--squash", "--match-head-commit", HEAD] in gh_calls(merge_remote)
    assert not any("--delete-branch" in row for row in gh_calls(merge_remote))
    assert "Local cleanup: keep this worktree and local branch" in result.stdout


@pytest.mark.parametrize(
    "kind,status,message",
    [
        ("GH_MERGE", 1, "required checks have not passed"),
        ("GH_VIEW", 1, "no pull requests found for branch"),
        ("GIT_HEAD", 128, "unable to resolve HEAD"),
        ("GIT_ROOT", 128, "not a git repository"),
    ],
)
def test_original_error_remains_visible(
    run_cli: CliRunner, merge_remote: Path, kind: str, status: int, message: str
) -> None:
    result = run_cli(
        SCRIPT, str(merge_remote), payload="\n\n", env={f"{kind}_EXIT_CODE": str(status), f"{kind}_ERROR": message}
    )
    assert result.returncode == status
    assert message in result.stderr
    assert "Press Enter or Esc to close" in result.stdout
    if kind != "GH_MERGE":
        assert not any(row[:2] == ["pr", "merge"] for row in gh_calls(merge_remote))
    if kind == "GIT_ROOT":
        assert not gh_calls(merge_remote)
