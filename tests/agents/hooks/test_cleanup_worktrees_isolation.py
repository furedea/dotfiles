"""Untrusted worktree metadata and Git configuration cannot affect cleanup or current detection."""

import os
from pathlib import Path
import shlex
import shutil

import pytest
import pytest_mock

from tests.agents.hooks.cleanup_worktrees_runtime import branches, cleanup, git, task_worktree

import cleanup_worktrees


@pytest.mark.parametrize("planted", ["commondir", "both"])
def test_lane_status_never_runs_a_filter_from_raced_admin_configuration(
    primary: Path, merged: dict[str, str], tmp_path: Path, planted: str
) -> None:
    path = task_worktree(primary, "feat/race")
    (path / ".gitattributes").write_text("README.md filter=planted\n")
    git("add", ".gitattributes", cwd=path)
    git("commit", "--quiet", "-m", "Add filter attribute", cwd=path)
    worktree = next(tree for tree in cleanup_worktrees.linked_worktrees(primary) if tree.path == path)
    admin = worktree.admin_dir
    assert admin is not None
    fake = tmp_path / "fake.git"
    shutil.copytree(primary / ".git", fake)
    git("config", "--file", str(fake / "config"), "extensions.worktreeConfig", "true", cwd=primary)
    marker = tmp_path / "clean-filter-ran"
    filter_command = f"touch {shlex.quote(str(marker))}; cat"
    git("config", "--file", str(fake / "config"), "filter.planted.clean", filter_command, cwd=primary)
    config = tmp_path / "config.worktree"
    git("config", "--file", str(config), "filter.planted.clean", filter_command, cwd=primary)
    readme = path / "README.md"
    readme.unlink()
    readme.write_text("base\n")
    index_time = (admin / "index").stat().st_mtime_ns
    os.utime(readme, ns=(index_time, index_time))
    executable = shutil.which("git")
    assert executable
    rewrite = ""
    if planted in {"commondir", "both"}:
        rewrite += f"printf '%s' {shlex.quote(str(fake))} > {shlex.quote(str(admin / 'commondir'))}\n"
    if planted in {"config.worktree", "both"}:
        rewrite += f"cp {shlex.quote(str(config))} {shlex.quote(str(admin / 'config.worktree'))}\n"
    wrapper = tmp_path / "bin/git"
    wrapper.write_text(
        '#!/bin/sh\ncase " $* " in *" status "*)\n' + rewrite + f';; esac\nexec {shlex.quote(executable)} "$@"\n'
    )
    wrapper.chmod(0o755)

    assert cleanup_worktrees.worktree_is_clean(primary, worktree)

    assert not marker.exists()
    if planted in {"commondir", "both"}:
        assert (admin / "commondir").read_text() == str(fake)
    if planted in {"config.worktree", "both"}:
        assert (admin / "config.worktree").exists()


def test_git_index_file_is_not_inherited(
    primary: Path, merged: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = task_worktree(primary, "feat/done")
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=path)
    index = tmp_path / "planted-index"
    monkeypatch.setenv("GIT_INDEX_FILE", str(index))

    result = cleanup(primary)

    assert result.returncode == 0
    assert not path.exists()
    assert not index.exists()
    monkeypatch.delenv("GIT_INDEX_FILE")
    assert branches(primary) == {"main"}


def test_lane_git_uses_the_primary_common_directory(
    primary: Path, merged: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = task_worktree(primary, "feat/lane")
    worktree = next(tree for tree in cleanup_worktrees.linked_worktrees(primary) if tree.path == path)
    record = tmp_path / "git-environment"
    wrapper = tmp_path / "bin/git"
    wrapper.write_text(
        '#!/bin/sh\nprintf "%s|%s\\n" "$GIT_COMMON_DIR" "$GIT_CONFIG_NOSYSTEM" >> ' + shlex.quote(str(record)) + "\n"
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("GIT_COMMON_DIR", str(tmp_path / "planted"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "0")

    assert cleanup_worktrees.worktree_is_clean(primary, worktree)

    assert record.read_text().splitlines() == [f"{primary / '.git'}|1"] * 2


@pytest.mark.parametrize("executable", ["git", "gh"])
def test_run_removes_inherited_git_environment_variables_and_preserves_the_rest(
    primary: Path, monkeypatch: pytest.MonkeyPatch, mocker: pytest_mock.MockerFixture, executable: str
) -> None:
    monkeypatch.setenv("GIT_INDEX_FILE", "/planted-index")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "/planted-monitor")
    monkeypatch.setenv("CLEANUP_TEST", "preserved")
    process = mocker.patch("cleanup_worktrees.subprocess.run", autospec=True)
    process.return_value.stdout = ""

    cleanup_worktrees.run(executable, "status", cwd=primary)

    expected = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    if executable == "git":
        expected.update(GIT_COMMON_DIR=str(primary / ".git"), GIT_CONFIG_NOSYSTEM="1")
    assert process.call_args.kwargs["env"] == expected


def test_lane_status_disables_submodules_and_lfs_filters(primary: Path, mocker: pytest_mock.MockerFixture) -> None:
    path = task_worktree(primary, "feat/lane")
    worktree = next(tree for tree in cleanup_worktrees.linked_worktrees(primary) if tree.path == path)
    process = mocker.patch("cleanup_worktrees.subprocess.run", autospec=True)
    process.return_value.stdout = ""

    assert cleanup_worktrees.worktree_is_clean(primary, worktree)

    status = process.call_args.args[0]
    assert "status" in status
    assert "--ignore-submodules=all" in status
    for setting in (
        "extensions.worktreeConfig=false",
        "diff.ignoreSubmodules=all",
        "filter.lfs.process=",
        "filter.lfs.clean=",
        "filter.lfs.smudge=",
    ):
        assert any(status[index : index + 2] == ("-c", setting) for index in range(len(status) - 1))


def test_a_gitlink_worktree_is_skipped_without_running_submodule_git(
    primary: Path, merged: dict[str, str], tmp_path: Path
) -> None:
    path = task_worktree(primary, "feat/submodule")
    (path / ".gitattributes").write_text("README.md filter=planted\n")
    git("add", ".gitattributes", cwd=path)
    git("commit", "--quiet", "-m", "Add filter attribute", cwd=path)
    head = git("rev-parse", "HEAD", cwd=path)
    git("update-index", "--add", "--cacheinfo", f"160000,{head},submodule", cwd=path)
    git("commit", "--quiet", "-m", "Add gitlink", cwd=path)
    merged["feat/submodule"] = git("rev-parse", "HEAD", cwd=path)
    submodule = path / "submodule"
    git("clone", "--quiet", str(primary), str(submodule), cwd=primary)
    git("checkout", "--quiet", head, cwd=submodule)
    marker = tmp_path / "submodule-git-ran"
    git("config", "filter.planted.clean", f"touch {shlex.quote(str(marker))}; cat", cwd=submodule)
    readme = submodule / "README.md"
    readme.unlink()
    readme.write_text("base\n")
    git("status", "--porcelain", cwd=submodule)
    assert marker.exists()
    marker.unlink()
    readme.unlink()
    readme.write_text("base\n")

    result = cleanup(primary, "--dry-run")

    assert result.returncode == 0
    assert not marker.exists()
    assert "remove worktree" not in result.stdout
    assert path.exists()
    assert "feat/submodule" in branches(primary)


def test_a_worktree_with_a_replaced_git_file_is_skipped(primary: Path, merged: dict[str, str], tmp_path: Path) -> None:
    path = task_worktree(primary, "feat/planted")
    merged["feat/planted"] = git("rev-parse", "HEAD", cwd=path)
    fake = tmp_path / "fake"
    git("clone", "--quiet", "--no-checkout", str(primary), str(fake), cwd=primary)
    git(f"--git-dir={fake / '.git'}", "read-tree", merged["feat/planted"], cwd=primary)
    (path / ".git").write_text(f"gitdir: {fake / '.git'}\n")

    result = cleanup(primary, "--dry-run")

    assert result.returncode == 0
    assert "remove worktree" not in result.stdout
    assert path.exists()
    assert "feat/planted" in branches(primary)


@pytest.mark.parametrize("planted", ["commondir", "config.worktree"])
def test_a_worktree_with_untrusted_admin_configuration_is_skipped(
    primary: Path, merged: dict[str, str], tmp_path: Path, planted: str
) -> None:
    path = task_worktree(primary, "feat/planted")
    merged["feat/planted"] = git("rev-parse", "HEAD", cwd=path)
    admin = Path(git("rev-parse", "--absolute-git-dir", cwd=path))
    if planted == "commondir":
        fake = tmp_path / "fake.git"
        shutil.copytree(primary / ".git", fake)
        (admin / "commondir").write_text(str(fake))
    else:
        (admin / "config.worktree").write_text("[core]\n\tbare = false\n")

    result = cleanup(primary, "--dry-run")

    assert result.returncode == 0
    assert "remove worktree" not in result.stdout
    assert path.exists()
    assert "feat/planted" in branches(primary)


@pytest.mark.parametrize("entry", ["primary", "lane", "session-start", "sweep"])
@pytest.mark.parametrize("config", ["shared", "worktree"])
def test_lane_fsmonitor_is_never_executed_and_git_and_gh_run_from_the_primary(
    primary: Path,
    merged: dict[str, str],
    tmp_path: Path,
    entry: str,
    config: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = task_worktree(primary, "feat/planted")
    current = task_worktree(primary, "feat/current")
    if entry == "sweep":
        home = tmp_path / "home"
        lane = home / ".herdr/worktrees/repo/feat-planted"
        lane.parent.mkdir(parents=True)
        git("worktree", "move", str(path), str(lane), cwd=primary)
        path = lane
        monkeypatch.setenv("HOME", str(home))
    merged["feat/planted"] = git("rev-parse", "HEAD", cwd=path)
    marker = tmp_path / "fsmonitor-ran"
    # Inherited command-line config must not mask the planted monitor.
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)
    monkeypatch.delenv("GIT_CONFIG_PARAMETERS", raising=False)
    monitor = tmp_path / "monitor"
    monitor.write_text(f"#!/bin/sh\ntouch {shlex.quote(str(marker))}\n")
    monitor.chmod(0o755)
    if config == "worktree":
        git("config", "extensions.worktreeConfig", "true", cwd=primary)
    git("config", *(["--worktree"] if config == "worktree" else []), "core.fsmonitor", str(monitor), cwd=path)
    discovery = tmp_path / "lane-discovery"
    for name in ("git", "gh"):
        executable = shutil.which(name)
        assert executable
        wrapper = tmp_path / "bin" / name
        if name == "gh":
            wrapper.rename(tmp_path / "original-gh")
            executable = str(tmp_path / "original-gh")
        wrapper.write_text(
            f'#!/bin/sh\ncase "$PWD" in {shlex.quote(str(path))}*|{shlex.quote(str(current))}*) '
            f'touch {shlex.quote(str(discovery))}; exit 99;; esac\nexec {shlex.quote(executable)} "$@"\n'
        )
        wrapper.chmod(0o755)

    if entry in {"session-start", "sweep"}:
        result = cleanup(tmp_path, "session-start", payload={"cwd": str(tmp_path if entry == "sweep" else current)})
    else:
        result = cleanup(primary if entry == "primary" else current)

    assert result.returncode == 0
    assert not marker.exists()
    assert not discovery.exists()
    assert path.exists() == (config == "worktree")
    assert current.exists()


def test_the_primary_and_current_checkouts_are_never_removed(primary: Path, merged: dict[str, str]) -> None:
    path = task_worktree(primary, "feat/here")
    merged["feat/here"] = git("rev-parse", "HEAD", cwd=path)
    merged["main"] = git("rev-parse", "HEAD", cwd=primary)
    cleanup(path)
    assert path.exists()
    assert primary.exists()
    assert {"main", "feat/here"} <= branches(primary)


@pytest.mark.parametrize("planted", ["file", "directory"])
def test_a_planted_git_entry_inside_a_lane_is_neither_current_nor_primary(
    primary: Path, merged: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, planted: str
) -> None:
    home = tmp_path / "home"
    path = home / ".herdr/worktrees/repo/feat-here"
    path.parent.mkdir(parents=True)
    original = task_worktree(primary, "feat/here")
    git("worktree", "move", str(original), str(path), cwd=primary)
    nested = path / "nested"
    nested.mkdir()
    (nested / "tracked.txt").write_text("tracked\n")
    git("add", ".", cwd=path)
    git("commit", "--quiet", "-m", "Add nested directory", cwd=path)
    merged["feat/here"] = git("rev-parse", "HEAD", cwd=path)
    other = task_worktree(primary, "feat/done")
    merged["feat/done"] = git("rev-parse", "HEAD", cwd=other)
    if planted == "file":
        (nested / ".git").write_text((path / ".git").read_text())
    else:
        git("init", "--quiet", cwd=nested)
    monkeypatch.setenv("HOME", str(home))
    marker = tmp_path / "nested-git-ran"
    executable = shutil.which("git")
    assert executable
    wrapper = tmp_path / "bin/git"
    wrapper.write_text(
        f'#!/bin/sh\nif [ "$PWD" = {shlex.quote(str(nested))} ]; then '
        f'touch {shlex.quote(str(marker))}; exit 99; fi\nexec {shlex.quote(executable)} "$@"\n'
    )
    wrapper.chmod(0o755)

    result = cleanup(nested)

    assert result.returncode == 0
    assert not marker.exists()
    assert path.exists()
    assert not other.exists()
    assert branches(primary) == {"main", "feat/here"}
    monkeypatch.setattr(cleanup_worktrees, "sandbox_writable_paths", set)
    assert cleanup_worktrees.toplevel(nested) == path
