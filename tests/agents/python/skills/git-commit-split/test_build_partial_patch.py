from pathlib import Path
import subprocess

import pytest

from tests.agents.python.conftest import load_script_module


build_partial_patch = load_script_module(
    "agents/skills/git-commit-split/scripts/build_partial_patch.py",
    "build_partial_patch",
)


DIFF_TEXT = """diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
-old
+new
@@ -10,2 +10,2 @@
-before
+after
diff --git a/readme.md b/readme.md
index 3333333..4444444 100644
--- a/readme.md
+++ b/readme.md
@@ -1 +1 @@
-Hello
+Hi
"""


def test_parse_diff_splits_files_and_hunks() -> None:
    files = build_partial_patch.parse_diff(DIFF_TEXT)

    assert [file["path"] for file in files] == ["app.py", "readme.md"]
    assert len(files[0]["hunks"]) == 2
    assert len(files[1]["hunks"]) == 1


def test_build_partial_keeps_selected_hunks_only() -> None:
    files = build_partial_patch.parse_diff(DIFF_TEXT)

    patch = build_partial_patch.build_partial(files, [{"file": "app.py", "hunks": [2]}])

    assert "diff --git a/app.py b/app.py" in patch
    assert "@@ -1,2 +1,2 @@" not in patch
    assert "@@ -10,2 +10,2 @@" in patch
    assert "diff --git a/readme.md b/readme.md" not in patch


def test_build_partial_exits_when_selection_references_missing_file() -> None:
    files = build_partial_patch.parse_diff(DIFF_TEXT)

    with pytest.raises(SystemExit) as error:
        build_partial_patch.build_partial(files, [{"file": "missing.py", "hunks": "all"}])

    assert error.value.code == 2


@pytest.mark.parametrize("filename", ["file with spaces.py", "日本語.py", 'quote"name.py', "tab\tname.py"])
def test_partial_patch_applies_selected_hunks_for_git_quoted_paths(tmp_path: Path, filename: str) -> None:
    run_git(tmp_path, "init", "--quiet")
    target = tmp_path / filename
    target.write_text("one\nkeep\nkeep\nkeep\ntwo\n")
    run_git(tmp_path, "add", "--", filename)
    target.write_text("ONE\nkeep\nkeep\nkeep\nTWO\n")
    diff = run_git(tmp_path, "diff", "--no-ext-diff", "--no-color", "-U0", "--src-prefix=i/", "--dst-prefix=w/")

    files = build_partial_patch.parse_diff(diff)
    patch = build_partial_patch.build_partial(files, [{"file": filename, "hunks": [1]}])
    run_git(tmp_path, "apply", "--cached", "--unidiff-zero", "-", patch=patch)

    assert run_git(tmp_path, "show", f":{filename}") == "ONE\nkeep\nkeep\nkeep\ntwo\n"
    assert target.read_text() == "ONE\nkeep\nkeep\nkeep\nTWO\n"


@pytest.mark.parametrize("filename", ["binary with spaces.bin", "日本語.bin"])
def test_partial_patch_preserves_binary_diffs_without_file_markers(tmp_path: Path, filename: str) -> None:
    run_git(tmp_path, "init", "--quiet")
    target = tmp_path / filename
    target.write_bytes(b"old\0content\n")
    run_git(tmp_path, "add", "--", filename)
    target.write_bytes(b"new\0content\n")
    diff = run_git(tmp_path, "diff", "--no-ext-diff", "--no-color", "--binary")

    files = build_partial_patch.parse_diff(diff)
    patch = build_partial_patch.build_partial(files, [{"file": filename, "hunks": "all"}])
    run_git(tmp_path, "apply", "--cached", "-", patch=patch)

    assert run_git(tmp_path, "show", f":{filename}") == "new\0content\n"


def test_partial_patch_selects_a_pure_rename_by_its_destination(tmp_path: Path) -> None:
    run_git(tmp_path, "init", "--quiet")
    old_path = tmp_path / "old name.txt"
    old_path.write_text("unchanged\n")
    run_git(tmp_path, "add", "--", old_path.name)
    new_path = tmp_path / "新しい名前.txt"
    old_path.rename(new_path)
    run_git(tmp_path, "add", "-N", "--", new_path.name)
    diff = run_git(tmp_path, "diff", "--no-ext-diff", "--no-color", "-M")

    files = build_partial_patch.parse_diff(diff)
    patch = build_partial_patch.build_partial(files, [{"file": new_path.name, "hunks": "all"}])

    assert len(files) == 1
    assert files[0]["hunks"] == []
    assert patch == diff


def run_git(repo: Path, *arguments: str, patch: str | None = None) -> str:
    return subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(repo), *arguments],
        input=patch,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
