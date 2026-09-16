from pathlib import Path
import subprocess

import pytest

from tests.runtime import load_script_module


snapshot = load_script_module("agents/hooks/lib/session_snapshot.py", "session_snapshot")


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    (root / "source.py").write_text("already dirty\n")
    (root / ".gitignore").write_text("output/\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    (root / "source.py").write_text("preexisting edit\n")
    return root


def test_start_state_excludes_preexisting_changes_without_a_commit_or_remote(repository: Path) -> None:
    baseline = snapshot.capture(repository)
    assert baseline.changed_paths(snapshot.capture(repository)) == ()
    assert "preexisting edit" not in str(baseline.to_json())


@pytest.mark.parametrize("change", ["edit", "add", "delete", "rename", "executable"])
def test_content_and_file_identity_changes_are_selected(repository: Path, change: str) -> None:
    baseline = snapshot.capture(repository)
    source = repository / "source.py"
    expected = ("source.py",)
    if change == "edit":
        source.write_text("task edit\n")
    elif change == "add":
        (repository / "new\n file.py").write_text("new\n")
        expected = ("new\n file.py",)
    elif change == "delete":
        source.unlink()
    elif change == "rename":
        source.rename(repository / "renamed.py")
        expected = ("renamed.py", "source.py")
    else:
        source.chmod(0o755)
    current = snapshot.capture(repository)
    assert baseline.changed_paths(current) == expected
    assert current.digest != baseline.digest


def test_generated_ignored_files_do_not_require_tests(repository: Path) -> None:
    baseline = snapshot.capture(repository)
    (repository / "output").mkdir()
    (repository / "output/result.py").write_text("generated")
    assert baseline.changed_paths(snapshot.capture(repository)) == ()


def test_restoring_content_restores_snapshot(repository: Path) -> None:
    baseline = snapshot.capture(repository)
    (repository / "source.py").write_text("temporary change\n")
    (repository / "source.py").write_text("preexisting edit\n")
    assert snapshot.capture(repository).digest == baseline.digest


def test_external_symlink_cannot_supply_stale_evidence(repository: Path, tmp_path: Path) -> None:
    target = tmp_path / "external.py"
    target.write_text("outside")
    (repository / "link.py").symlink_to(target)
    with pytest.raises(snapshot.SnapshotError, match="outside"):
        snapshot.capture(repository)
