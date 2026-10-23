"""Lane metadata never authorizes commands in a sandbox-writable primary."""

import json
import os
from pathlib import Path
import shlex
import shutil
import tempfile
from collections.abc import Iterator

import pytest

from tests.agents.hooks.cleanup_worktrees_runtime import (
    branches,
    cleanup,
    cleanup_with_real_policy,
    git,
    task_worktree,
)

import cleanup_worktrees


@pytest.fixture
def temporary(tmp_path: Path, merged: dict[str, str], location: str) -> Iterator[Path]:
    if location not in {"tmp", "private-tmp"}:
        yield tmp_path
        return

    # The merged fixture points TMPDIR at this disposable sandbox directory.
    sandbox_tmp = tmp_path / "sandbox-tmp"
    sandbox_tmp.mkdir()
    candidates = [Path("/tmp"), Path("/private/tmp"), Path("/tmp/claude"), Path("/private/tmp/claude")]
    candidates.append(Path(os.environ["TMPDIR"]))
    failures = []
    for candidate in dict.fromkeys(candidates):
        try:
            directory = tempfile.TemporaryDirectory(dir=candidate)
        except OSError as error:
            failures.append(f"{candidate}: {error}")
            continue
        with directory:
            yield Path(directory.name)
        return
    pytest.skip("No writable temporary directory inside the production writable locations: " + "; ".join(failures))


def herdr_lane(primary: Path) -> Path:
    lane = Path.home() / ".herdr/worktrees/repo/feat-done"
    lane.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "--quiet", "-b", "feat/done", str(lane), cwd=primary)
    return lane


def record_commands(tmp_path: Path, forbidden: Path) -> Path:
    marker = tmp_path / "untrusted-command"
    for name in ("git", "gh"):
        executable = shutil.which(name)
        assert executable
        wrapper = tmp_path / "bin" / name
        if name == "gh":
            original = tmp_path / "original-gh"
            wrapper.rename(original)
            executable = str(original)
        wrapper.write_text(
            f'#!/bin/sh\nprintf "%s %s %s\\n" "$PWD" {name} "$*" >> {shlex.quote(str(tmp_path / "commands"))}\n'
            f'case "$PWD $*" in *{shlex.quote(str(forbidden))}*) '
            f"touch {shlex.quote(str(marker))}; exit 99;; esac\n"
            f'exec {shlex.quote(executable)} "$@"\n'
        )
        wrapper.chmod(0o755)
    return marker


@pytest.mark.parametrize("entry", ["sweep", "caller"])
@pytest.mark.parametrize(
    "location",
    ["tmp", "private-tmp", "tmpdir", "tmpdir-symlink", "allow-write", "relative", "tilde", "symlink", "herdr"],
)
def test_lane_metadata_cannot_authorize_a_sandbox_writable_primary(
    primary: Path,
    merged: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    location: str,
    temporary: Path,
    entry: str,
) -> None:
    fake = tmp_path / "fake"
    entries = []
    if location in {"tmp", "private-tmp"}:
        fake = Path(temporary) / "fake"
    elif location.startswith("tmpdir"):
        monkeypatch.setenv("TMPDIR", str(fake.parent / "temp-link" if location.endswith("symlink") else fake))
        if location.endswith("symlink"):
            (fake.parent / "temp-link").symlink_to(fake, target_is_directory=True)
    elif location == "herdr":
        fake = Path.home() / ".herdr/worktrees/fake/primary"
    elif location in {"relative", "tilde"}:
        fake = Path.home() / "writable/fake"
        entries = ["~/writable" if location == "tilde" else "writable"]
    else:
        entries = [str(fake)]
    fake.parent.mkdir(parents=True, exist_ok=True)
    git("clone", "--quiet", str(primary), str(fake), cwd=primary)
    lane = herdr_lane(fake)
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=lane)
    if location == "tmp" and fake.resolve().is_relative_to(Path("/tmp").resolve()):
        alias = Path("/tmp") / fake.resolve().relative_to(Path("/tmp").resolve())
        (lane / ".git").write_text((lane / ".git").read_text().replace(str(fake), str(alias)))
    if location == "symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(fake, target_is_directory=True)
        (lane / ".git").write_text((lane / ".git").read_text().replace(str(fake), str(alias)))
    settings = Path.home() / ".claude/settings.json"
    settings.write_text(json.dumps({"sandbox": {"filesystem": {"allowWrite": entries}}}))
    marker = record_commands(tmp_path, fake)

    result = cleanup_with_real_policy(tmp_path if entry == "sweep" else fake)

    assert result.returncode == 0
    assert not marker.exists()
    assert lane.exists()
    assert not (tmp_path / "commands").exists()


def test_lane_metadata_can_identify_another_trusted_primary(
    primary: Path, merged: dict[str, str], tmp_path: Path
) -> None:
    other = tmp_path / "other"
    git("clone", "--quiet", str(primary), str(other), cwd=primary)
    lane = herdr_lane(other)
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=lane)

    result = cleanup(tmp_path)

    assert result.returncode == 0
    assert not lane.exists()
    assert branches(other) == {"main"}


@pytest.mark.parametrize("settings", ["unreadable", "invalid", "invalid-shape"])
def test_unknown_writable_paths_skip_lane_primaries_but_clean_the_callers_repository(
    primary: Path, merged: dict[str, str], tmp_path: Path, settings: str
) -> None:
    other = tmp_path / "other"
    git("clone", "--quiet", str(primary), str(other), cwd=primary)
    lane = herdr_lane(other)
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=lane)
    own = task_worktree(primary, "feat/own")
    merged["feat/own"] = git("rev-parse", "HEAD", cwd=own)
    path = Path.home() / ".claude/settings.json"
    if settings == "unreadable":
        path.unlink()
        path.mkdir()
    else:
        path.write_text("not json" if settings == "invalid" else '{"sandbox":null}')
    marker = record_commands(tmp_path, other)

    assert cleanup(lane).returncode == 0
    assert not marker.exists()
    result = cleanup(primary)

    assert result.returncode == 0
    assert not marker.exists()
    assert lane.exists()
    assert not own.exists()
    assert branches(primary) == {"main"}


@pytest.mark.parametrize("entry", ["file", "symlink"])
def test_a_primary_without_a_real_git_directory_is_never_used(
    primary: Path, merged: dict[str, str], tmp_path: Path, entry: str
) -> None:
    lane = herdr_lane(primary)
    admin = primary / ".git"
    relocated = primary / "relocated"
    admin.rename(relocated)
    if entry == "symlink":
        admin.symlink_to(relocated, target_is_directory=True)
    else:
        admin.write_text(f"gitdir: {relocated}\n")
    marker = record_commands(tmp_path, primary)

    assert cleanup(primary).returncode == 0
    assert not marker.exists()
    assert lane.exists()


@pytest.mark.parametrize("field", ["gitdir", "lane-git", "commondir"])
def test_primary_worktree_records_must_point_both_ways_before_any_lane_command(
    primary: Path, merged: dict[str, str], tmp_path: Path, field: str
) -> None:
    lane = task_worktree(primary, "feat/done")
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=lane)
    admin = Path(git("rev-parse", "--absolute-git-dir", cwd=lane))
    if field == "lane-git":
        (lane / ".git").write_text(f"gitdir: {primary / '.git'}\n")
    else:
        (admin / field).write_text(str(tmp_path / "elsewhere"))

    assert cleanup(primary).returncode == 0
    assert lane.exists()
    assert "feat/done" in branches(primary)


def test_git_removal_is_isolated_and_herdr_only_closes_the_workspace(
    primary: Path, merged: dict[str, str], tmp_path: Path
) -> None:
    lane = task_worktree(primary, "feat/done")
    worktree = next(tree for tree in cleanup_worktrees.linked_worktrees(primary) if tree.path == lane)
    # The process wrapper rejects any invocation missing the required isolation.
    executable = shutil.which("git")
    assert executable
    wrapper = tmp_path / "bin/git"
    wrapper.write_text(
        '#!/bin/sh\ncase " $* " in *" worktree remove "*)\n'
        f'[ "$PWD" = {shlex.quote(str(primary))} ] || exit 99\n'
        f'for required in "--git-dir={primary / ".git"}" "--work-tree={primary}" '
        '"core.fsmonitor=false" "core.hooksPath=/dev/null"; do\n'
        'case " $* " in *" $required "*) ;; *) exit 99;; esac\ndone;; esac\n'
        f'exec {shlex.quote(executable)} "$@"\n'
    )
    wrapper.chmod(0o755)
    (tmp_path / "herdr_worktrees.json").write_text(
        json.dumps({"result": {"worktrees": [{"path": str(lane), "open_workspace_id": "w9"}]}})
    )

    cleanup_worktrees.remove_worktree(primary, worktree, "w9")

    assert not lane.exists()
    assert (tmp_path / "herdr_removed.txt").read_text().splitlines() == ["workspace close w9"]


def test_production_writable_paths_include_all_untrusted_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    alias = tmp_path / "alias"
    target = tmp_path / "target"
    target.mkdir()
    alias.symlink_to(target, target_is_directory=True)
    entries = [str(alias), "relative", "~/tilde"]
    (home / ".claude/settings.json").write_text(json.dumps({"sandbox": {"filesystem": {"allowWrite": entries}}}))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "temporary"))

    writable = cleanup_worktrees.sandbox_writable_paths()

    expected = {
        Path("/tmp"),
        Path("/private/tmp"),
        Path("/tmp/claude"),
        Path("/private/tmp/claude"),
        home / ".herdr/worktrees",
        tmp_path / "temporary",
        alias,
        home / "relative",
        home / "tilde",
    }
    assert writable is not None
    assert expected | {path.resolve() for path in expected} <= writable


@pytest.mark.parametrize("entry", ["sweep", "caller"])
def test_fixture_policy_still_rejects_a_planted_writable_primary(
    primary: Path, merged: dict[str, str], tmp_path: Path, entry: str
) -> None:
    fake = tmp_path / "writable/fake"
    fake.parent.mkdir()
    git("clone", "--quiet", str(primary), str(fake), cwd=primary)
    lane = herdr_lane(fake)
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=lane)
    marker = record_commands(tmp_path, fake)

    result = cleanup(tmp_path if entry == "sweep" else fake)

    assert result.returncode == 0
    assert not marker.exists()
    assert not (tmp_path / "commands").exists()
    assert lane.exists()
