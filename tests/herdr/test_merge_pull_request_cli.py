"""Approve-and-merge confirmation and failure visibility at the actual stdin/process boundary."""

import json
from pathlib import Path

import pytest

from tests.runtime import CliRunner, StubWriter


SCRIPT = "herdr/merge_pull_request.py"
HEAD = "0123456789abcdef0123456789abcdef01234567"
OTHER_HEAD = "fedcba9876543210fedcba9876543210fedcba98"
MERGE = ["pr", "merge", "--squash", "--delete-branch", "--match-head-commit", HEAD]
APPROVE = ["pr", "review", "42", "--approve"]


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
        kinds = {"view": "VIEW", "merge": "MERGE", "review": "REVIEW", "user": "USER"}
        assert args[:2] in (["pr", "view"], ["pr", "merge"], ["pr", "review"], ["api", "user"])
        kind = kinds[args[1]]
        status = int(os.environ.get(f"GH_{kind}_EXIT_CODE", "0"))
        if status:
            print(os.environ[f"GH_{kind}_ERROR"], file=sys.stderr)
            sys.exit(status)
        if kind == "USER":
            print("furedea")
        if kind == "VIEW":
            head = os.environ.get("PR_HEAD", os.environ["GIT_HEAD"])
            check = {
                "success": {"status": "COMPLETED", "conclusion": "SUCCESS"},
                "failure": {"status": "COMPLETED", "conclusion": "FAILURE"},
                "pending": {"status": "IN_PROGRESS", "conclusion": ""},
            }[os.environ.get("PR_CHECKS", "success")]
            approved = os.environ.get("PR_APPROVED_OID")
            reviews = [{"author": {"login": "furedea"}, "state": "APPROVED", "commit": {"oid": approved}}] if approved else []
            print(json.dumps({
                "number": 42,
                "title": "Merge helper",
                "baseRefName": "main",
                "headRefName": "feature/test",
                "headRefOid": head,
                "author": {"login": os.environ.get("PR_AUTHOR", "furedea-agent")},
                "latestReviews": reviews,
                "statusCheckRollup": [check, {"status": "COMPLETED", "conclusion": "SKIPPED"}],
            }))
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


def mutations(root: Path) -> list[list[str]]:
    return [row for row in gh_calls(root) if row[:2] in (["pr", "merge"], ["pr", "review"])]


@pytest.mark.parametrize(
    "key,confirm", [("\n", True), ("\r\n", True), ("\x1b\n", False), ("\x03\n", False), ("", False), ("x\n", False)]
)
def test_confirmation_keys(run_cli: CliRunner, merge_remote: Path, key: str, confirm: bool) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload=key)
    assert result.returncode == 0, result.stderr
    if confirm:
        assert mutations(merge_remote) == [APPROVE, MERGE]
        assert not any("--auto" in row or "--admin" in row for row in gh_calls(merge_remote))
    else:
        assert "Cancelled." in result.stdout
        assert not mutations(merge_remote)
    assert "PR #42: Merge helper" in result.stdout
    assert "feature/test -> main" in result.stdout
    assert "Enter / Ctrl+M  Approve and squash-merge now" in result.stdout
    if key == "x\n":
        assert "Press Enter or Esc to close" in result.stdout


def test_summary_shows_author_checks_and_approval(run_cli: CliRunner, merge_remote: Path) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload="\x1b")
    assert "Author: furedea-agent" in result.stdout
    assert "Checks: passed" in result.stdout
    assert "Approval: not yet approved" in result.stdout


def test_current_head_approval_is_not_repeated(run_cli: CliRunner, merge_remote: Path) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload="\n", env={"PR_APPROVED_OID": HEAD})
    assert result.returncode == 0, result.stderr
    assert mutations(merge_remote) == [MERGE]
    assert "Approval: approved by you" in result.stdout


def test_stale_approval_is_renewed(run_cli: CliRunner, merge_remote: Path) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload="\n", env={"PR_APPROVED_OID": OTHER_HEAD})
    assert result.returncode == 0, result.stderr
    assert mutations(merge_remote) == [APPROVE, MERGE]


def test_failed_approval_prevents_merge(run_cli: CliRunner, merge_remote: Path) -> None:
    result = run_cli(
        SCRIPT,
        str(merge_remote),
        payload="\n\n",
        env={"GH_REVIEW_EXIT_CODE": "1", "GH_REVIEW_ERROR": "approve not permitted"},
    )
    assert result.returncode == 1
    assert "approve not permitted" in result.stderr
    assert mutations(merge_remote) == [APPROVE]
    assert "Press Enter or Esc to close" in result.stdout


@pytest.mark.parametrize(
    "env,reason",
    [
        ({"PR_HEAD": OTHER_HEAD}, "local HEAD does not match the pull request head"),
        ({"PR_CHECKS": "failure"}, "required checks have not all succeeded"),
        ({"PR_CHECKS": "pending"}, "required checks have not all succeeded"),
    ],
)
@pytest.mark.parametrize("key", ["\n", "A"])
def test_unsafe_state_is_refused(
    run_cli: CliRunner, merge_remote: Path, env: dict[str, str], reason: str, key: str
) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload=key + "\n", env={**env, "PR_AUTHOR": "furedea"})
    assert result.returncode == 1
    assert f"Cannot merge: {reason}" in result.stdout
    assert "Press Enter or Esc to close" in result.stdout
    assert not mutations(merge_remote)


def test_own_pull_request_is_not_approved_or_bypassed_by_enter(run_cli: CliRunner, merge_remote: Path) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload="\n\n", env={"PR_AUTHOR": "furedea"})
    assert result.returncode == 0, result.stderr
    assert "admin bypass" in result.stdout
    assert "A               Merge with admin bypass" in result.stdout
    assert "Enter / Ctrl+M  Approve" not in result.stdout
    assert not mutations(merge_remote)


def test_own_pull_request_merges_with_admin_on_explicit_key(run_cli: CliRunner, merge_remote: Path) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload="A", env={"PR_AUTHOR": "furedea"})
    assert result.returncode == 0, result.stderr
    assert mutations(merge_remote) == [[*MERGE, "--admin"]]


def test_admin_key_is_ignored_for_other_authors(run_cli: CliRunner, merge_remote: Path) -> None:
    result = run_cli(SCRIPT, str(merge_remote), payload="A\n")
    assert not mutations(merge_remote)
    assert "Cancelled." in result.stdout


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
        ("GH_USER", 1, "not logged in"),
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
