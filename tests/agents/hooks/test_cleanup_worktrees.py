"""Merged task worktrees and branches are removed only when nothing unmerged would be lost."""

import json
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

from tests.agents.hooks.cleanup_worktrees_runtime import SCRIPT, branches, cleanup, git, task_worktree
from tests.runtime import real_git

import herdr_ownership
import session_store


def test_a_merged_clean_worktree_and_its_branch_are_removed(primary: Path, merged: dict[str, str]) -> None:
    path = task_worktree(primary, "feat/done")
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=path)
    assert cleanup(primary).returncode == 0
    assert not path.exists()
    assert branches(primary) == {"main"}


def test_removal_does_not_repeat_gits_cleanliness_check(primary: Path, merged: dict[str, str], tmp_path: Path) -> None:
    path = task_worktree(primary, "feat/done")
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=path)
    executable = real_git()
    wrapper = tmp_path / "bin/git"
    wrapper.write_text(
        '#!/bin/sh\ncase " $* " in *" worktree remove "*)\n'
        'case " $* " in *" --force "*) ;; *) exit 99;; esac;; esac\n'
        f'exec {shlex.quote(executable)} "$@"\n'
    )
    wrapper.chmod(0o755)

    result = cleanup(primary)

    assert result.returncode == 0
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
    assert (tmp_path / "herdr_removed.txt").read_text().split() == ["workspace", "close", "w9"]
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


@pytest.fixture
def recorded_primary(primary: Path, merged: dict[str, str], tmp_path: Path) -> None:
    record = session_store.register(primary, "codex", "parent-session")
    response = {
        "result": {
            "type": "workspace_created",
            "workspace": {"workspace_id": "w3", "label": "repo"},
            "root_pane": {"cwd": str(primary), "terminal_id": "term_primary"},
        }
    }
    herdr_ownership.confirm(
        record, f"herdr workspace create --cwd {primary} --label repo --no-focus", json.dumps(response)
    )
    row = {"workspace_id": "w3", "label": "repo", "worktree": {"checkout_path": str(primary)}}
    (tmp_path / "herdr_workspaces.json").write_text(json.dumps({"result": {"workspaces": [row]}}))


@pytest.mark.usefixtures("recorded_primary")
@pytest.mark.parametrize("dry_run", [False, True])
def test_an_idle_primary_stays_open_when_no_merged_worktrees_are_removed(
    primary: Path, tmp_path: Path, dry_run: bool
) -> None:
    result = cleanup(primary, *(["--dry-run"] if dry_run else []))
    assert result.returncode == 0
    assert "close primary workspace" not in result.stdout
    assert not (tmp_path / "herdr_removed.txt").exists()


@pytest.mark.usefixtures("recorded_primary")
def test_a_failed_primary_close_preserves_completed_removal_reports(
    primary: Path, merged: dict[str, str], tmp_path: Path
) -> None:
    path = task_worktree(primary, "feat/lane")
    merged["feat/lane"] = git("rev-parse", "HEAD", cwd=path)
    herdr = tmp_path / "bin/herdr"
    herdr.write_text(herdr.read_text().replace('echo "$@" >>', 'exit 1; echo "$@" >>', 1))
    result = cleanup(primary)
    assert result.returncode == 0
    assert not path.exists()
    assert branches(primary) == {"main"}
    assert f"remove worktree {path} and branch feat/lane" in result.stdout
    assert "failed to close primary workspace w3" in result.stdout
    assert not any(line.startswith("close primary workspace") for line in result.stdout.splitlines())


@pytest.mark.usefixtures("recorded_primary")
@pytest.mark.parametrize("dry_run", [False, True])
def test_an_agent_created_primary_closes_after_its_last_lane_is_removed(
    primary: Path, merged: dict[str, str], tmp_path: Path, dry_run: bool
) -> None:
    path = task_worktree(primary, "feat/lane")
    merged["feat/lane"] = git("rev-parse", "HEAD", cwd=path)
    result = cleanup(primary, *(["--dry-run"] if dry_run else []))
    assert result.returncode == 0
    assert "close primary workspace w3" in result.stdout
    if dry_run:
        assert path.exists()
        assert not (tmp_path / "herdr_removed.txt").exists()
    else:
        assert not path.exists()
        assert (tmp_path / "herdr_removed.txt").read_text().splitlines() == ["workspace close w3"]


@pytest.mark.usefixtures("recorded_primary")
@pytest.mark.parametrize("remaining", ["unmerged", "dirty", "current", "detached"])
def test_a_primary_stays_open_while_any_linked_checkout_remains(
    primary: Path, merged: dict[str, str], tmp_path: Path, remaining: str
) -> None:
    path = task_worktree(primary, "feat/remaining")
    if remaining != "unmerged":
        merged["feat/remaining"] = git("rev-parse", "HEAD", cwd=path)
    if remaining == "dirty":
        (path / "untracked.txt").write_text("work")
    if remaining == "detached":
        git("checkout", "--detach", cwd=path)
    for arguments in [[], ["--dry-run"]]:
        assert cleanup(path if remaining == "current" else primary, *arguments).returncode == 0
        assert path.exists()
        assert not (tmp_path / "herdr_removed.txt").exists()


@pytest.mark.usefixtures("recorded_primary")
@pytest.mark.parametrize("location", ["workspace", "terminal", "pane"])
def test_a_primary_with_an_agent_in_any_pane_stays_open(
    primary: Path, merged: dict[str, str], tmp_path: Path, location: str
) -> None:
    path = task_worktree(primary, "feat/lane")
    merged["feat/lane"] = git("rev-parse", "HEAD", cwd=path)
    agent = {
        "name": "busy",
        "workspace_id": "w3" if location == "workspace" else "",
        "terminal_id": "term_second" if location == "terminal" else "other",
        "pane_id": "p2" if location == "pane" else "other",
    }
    panes = [{"pane_id": "p1", "terminal_id": "term_primary"}, {"pane_id": "p2", "terminal_id": "term_second"}]
    (tmp_path / "herdr_panes.json").write_text(json.dumps({"result": {"panes": panes}}))
    (tmp_path / "herdr_agents.json").write_text(json.dumps({"result": {"agents": [agent]}}))
    assert cleanup(primary).returncode == 0
    assert not (tmp_path / "herdr_removed.txt").exists()


@pytest.mark.usefixtures("recorded_primary")
@pytest.mark.parametrize("mismatch", ["unrecorded", "label", "path", "terminal", "invalid record"])
def test_user_owned_or_replaced_primary_workspaces_stay_open(
    primary: Path, merged: dict[str, str], tmp_path: Path, mismatch: str
) -> None:
    path = task_worktree(primary, "feat/lane")
    merged["feat/lane"] = git("rev-parse", "HEAD", cwd=path)
    listing = tmp_path / "herdr_workspaces.json"
    value = json.loads(listing.read_text())
    row = value["result"]["workspaces"][0]
    if mismatch == "label":
        row["label"] = "user workspace"
    if mismatch == "path":
        row["worktree"]["checkout_path"] = str(tmp_path)
    if mismatch == "terminal":
        (tmp_path / "herdr_panes.json").write_text('{"result":{"panes":[]}}')
    if mismatch in {"unrecorded", "invalid record"}:
        record = session_store.session_directory(session_store.SessionKey(primary, "codex", "parent-session"))
        (record / ("herdr_agents.json" if mismatch == "unrecorded" else "baseline.json")).unlink()
    listing.write_text(json.dumps(value))
    assert cleanup(primary).returncode == 0
    assert not (tmp_path / "herdr_removed.txt").exists()


@pytest.mark.usefixtures("recorded_primary")
@pytest.mark.parametrize("listing", ["agents", "workspaces", "panes"])
@pytest.mark.parametrize("content", ["unavailable", '{"result":{}}', '{"result":{"agents":null}}'])
def test_a_primary_stays_open_when_live_state_cannot_be_verified(
    primary: Path, merged: dict[str, str], tmp_path: Path, listing: str, content: str
) -> None:
    path = task_worktree(primary, "feat/lane")
    merged["feat/lane"] = git("rev-parse", "HEAD", cwd=path)
    (tmp_path / f"herdr_{listing}.json").write_text(content)
    assert cleanup(primary).returncode == 0
    assert not (tmp_path / "herdr_removed.txt").exists()


@pytest.mark.usefixtures("recorded_primary")
@pytest.mark.parametrize("listing", ["panes", "agents"])
@pytest.mark.parametrize("field", ["terminal_id", "pane_id"])
@pytest.mark.parametrize("value", [["invalid"], {"invalid": "value"}])
def test_a_primary_stays_open_when_live_state_has_unhashable_values(
    primary: Path, merged: dict[str, str], tmp_path: Path, listing: str, field: str, value: object
) -> None:
    path = task_worktree(primary, "feat/lane")
    merged["feat/lane"] = git("rev-parse", "HEAD", cwd=path)
    rows = (
        [{"pane_id": "p1", "terminal_id": "term_primary"}, {field: value}] if listing == "panes" else [{field: value}]
    )
    (tmp_path / f"herdr_{listing}.json").write_text(json.dumps({"result": {listing: rows}}))
    result = cleanup(primary)
    assert result.returncode == 0
    assert not path.exists()
    assert f"remove worktree {path}" in result.stdout
    assert "close primary workspace" not in result.stdout
    assert not (tmp_path / "herdr_removed.txt").exists()
