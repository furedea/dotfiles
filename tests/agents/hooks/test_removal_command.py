"""rm passes only where every target is a literal path inside a temporary directory."""

from pathlib import Path
import subprocess

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")


@pytest.fixture
def project(git_project: Path, temporary_roots: Path) -> Path:
    """A repository with clean, modified, staged, and untracked files outside the temporary roots."""
    for name in ("tracked.txt", "modified.txt", "staged.txt"):
        (git_project / name).write_text("before")
    (git_project / "sub").mkdir()
    (git_project / "sub/nested.txt").write_text("before")
    git(git_project, "add", "tracked.txt", "modified.txt", "staged.txt", "sub/nested.txt")
    git(git_project, "commit", "--quiet", "-m", "files")
    (git_project / "modified.txt").write_text("after")
    (git_project / "staged.txt").write_text("after")
    git(git_project, "add", "staged.txt")
    (git_project / "untracked.txt").write_text("new")
    return temporary_roots


def git(directory: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=directory, check=True, capture_output=True)


def decide(kind: str, command: str, cwd: Path | None = None) -> str:
    payload: dict = {"tool_input": {"command": command}}
    if cwd:
        payload["cwd"] = str(cwd)
    return guard.decide(kind, payload).decision


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("rm {tmp}/a.txt", id="a file in the temporary directory"),
        pytest.param("rm -f {scratch}/session/a.txt {tmp}/b.txt", id="files in the scratchpad"),
        pytest.param("/bin/rm -- {tmp}/a.txt", id="rm invoked by path"),
        pytest.param("rm -rf {tmp}/build", id="a tree in the temporary directory"),
        pytest.param("rm -r -- {scratch}/a {tmp}/b", id="trees in both temporary roots"),
        pytest.param("rm -fR {tmp}/a/../b", id="a normalized path that stays inside"),
        pytest.param("ls {tmp} && rm -f {tmp}/a.txt; echo done", id="beside commands that only read"),
        pytest.param("command rm {tmp}/a.txt", id="behind a wrapper"),
        pytest.param("rm -f -- {tmp}/a_b-c.d/@x+y,z:1%2", id="every plain character"),
    ],
)
@pytest.mark.parametrize("kind", ["allowed", "forbidden"])
def test_removals_inside_a_temporary_root_pass(project: Path, kind: str, command: str) -> None:
    command = command.format(tmp=project / "tmp", scratch=project / "scratch")
    assert decide(kind, command) == "allow"


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("rm tracked.txt", id="a tracked file without changes, which git rm handles"),
        pytest.param("rm -f -- tracked.txt sub/nested.txt", id="several tracked files without changes"),
        pytest.param("/bin/rm tracked.txt", id="a tracked file by path"),
        pytest.param("command rm tracked.txt", id="a tracked file behind a wrapper"),
        pytest.param("rm modified.txt", id="a tracked file with unstaged changes"),
        pytest.param("rm staged.txt", id="a tracked file with staged changes"),
        pytest.param("rm untracked.txt", id="an untracked file"),
        pytest.param("rm tracked.txt untracked.txt", id="one unrestorable target among several"),
        pytest.param("rm $FILE", id="a run-time target"),
        pytest.param("rm *.txt", id="a glob"),
        pytest.param("rm $FLAGS tracked.txt", id="run-time options"),
        pytest.param("cd sub && rm tracked.txt", id="a relative target after the directory changes"),
        pytest.param("echo tracked.txt | xargs rm", id="targets read from input"),
        pytest.param("rm {tmp}/../outside.txt", id="a path that leaves the temporary directory"),
        pytest.param("rm --unknown tracked.txt", id="an unknown option"),
        pytest.param("rm", id="no targets"),
        pytest.param("printf x >> tracked.txt; rm tracked.txt", id="a write to the target first"),
        pytest.param("mv untracked.txt tracked.txt && rm tracked.txt", id="a move onto the target first"),
        pytest.param("ln -s {project} {tmp}/link; rm -r {tmp}/link/sub", id="a symlink created first"),
        pytest.param("rm tracked.txt; git checkout -- tracked.txt", id="any command that can write"),
        pytest.param("builtin cd sub && rm tracked.txt", id="a builtin directory change"),
        pytest.param("env --chdir=sub rm tracked.txt", id="env with a long directory option"),
        pytest.param("env -Csub rm tracked.txt", id="env with an attached directory option"),
        pytest.param("$GO sub; rm tracked.txt", id="a run-time program first"),
        pytest.param("{{ printf x; }} >> tracked.txt; rm tracked.txt", id="a write redirect on a block"),
        pytest.param("( printf x ) > tracked.txt; rm tracked.txt", id="a write redirect on a subshell"),
        pytest.param("if true; then printf x; fi >> tracked.txt; rm tracked.txt", id="a write redirect on an if"),
        pytest.param("while false; do :; done > tracked.txt; rm tracked.txt", id="a write redirect on a while"),
        pytest.param("for i in 1; do echo; done >> tracked.txt; rm tracked.txt", id="a write redirect on a for"),
        pytest.param("{{ ls; }} > {tmp}/out.txt; rm {tmp}/a.txt", id="any compound write beside rm"),
        pytest.param("rm '[t]racked.txt'", id="a quoted glob that Git would match against a tracked file"),
        pytest.param("rm ':(top)tracked.txt'", id="pathspec magic"),
        pytest.param("rm 'tracked*.txt'", id="a quoted wildcard"),
        pytest.param("rg --pre ./mk x {tmp}; rm {tmp}/a.txt", id="a search that runs a preprocessor"),
        pytest.param("/usr/bin/time -o {tmp}/a.txt ls; rm {tmp}/a.txt", id="a wrapper that writes a file"),
        pytest.param("rm ~/a.txt $HOME/b.txt", id="home directory paths"),
        pytest.param("rm -f {tmp}/{{a,../../../x}}", id="brace expansion that leaves the temporary directory"),
        pytest.param("rm {tmp}/a{{1..3}}.txt", id="a brace sequence"),
        pytest.param("rm {tmp}/{{a}}.txt", id="unquoted braces"),
        pytest.param("rm -f {tmp}/a/.\\\n./../../outside.txt", id="a line continuation that builds a parent step"),
        pytest.param("rm -f {tmp}/{{a,'b'}}", id="braces around a quoted part"),
    ],
)
def test_removals_outside_a_temporary_root_ask(project: Path, git_project: Path, command: str) -> None:
    command = command.format(tmp=project / "tmp", project=git_project)
    assert decide("allowed", command) == "ask"
    assert decide("forbidden", command) == "allow"


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("rm -rf build", id="a tree in the project"),
        pytest.param("rm -r tracked.txt", id="a tracked file removed recursively"),
        pytest.param("rm -r {tmp}/a build", id="one tree outside the temporary roots"),
        pytest.param("rm -rf $TARGET", id="a run-time tree"),
        pytest.param("rm -rf {tmp}", id="the temporary directory itself"),
        pytest.param("rm -rf {tmp}/../..", id="a path that climbs out"),
        pytest.param("rm build -rf", id="options after the operands"),
        pytest.param("rm --recursive build", id="the long option"),
        pytest.param("rm -rf {tmp}/{{a,../../../x}}", id="a tree named through brace expansion"),
        pytest.param("rm -rf {tmp}/a/.\\\n./../..", id="a tree named across a line continuation"),
        pytest.param("echo {tmp}/a | xargs rm -rf {tmp}/b", id="trees read from input"),
    ],
)
def test_recursive_removals_outside_the_temporary_roots_stay_denied(project: Path, command: str) -> None:
    command = command.format(tmp=project / "tmp")
    verdict = guard.decide("forbidden", {"tool_input": {"command": command}})
    assert verdict.decision == "deny"
    assert "directory trees" in verdict.reason


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("rm =tool", id="a zsh command-path expansion"),
        pytest.param("PATH=/repo/bin:$PATH; rm =tool", id="a zsh command-path expansion after PATH changes"),
        pytest.param("rm ~/x", id="a home directory path"),
        pytest.param("rm a.txt", id="a relative path"),
        pytest.param("rm ./sub/a.txt", id="a dot-relative path"),
    ],
)
def test_targets_that_are_not_absolute_literal_paths_ask_even_in_a_temporary_directory(
    project: Path, command: str
) -> None:
    temporary = project / "tmp"
    assert decide("allowed", command, cwd=temporary) == "ask"
    workdir = {"tool_input": {"command": command, "workdir": str(temporary)}, "cwd": str(temporary)}
    assert guard.decide("allowed", workdir).decision == "ask"


def test_a_recursive_zsh_command_path_expansion_stays_denied(project: Path) -> None:
    command = "PATH=/repo/bin:$PATH; rm -rf =tool"
    assert decide("forbidden", command, cwd=project / "tmp") == "deny"


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("rm {tmp}/tool", id="the same file as an absolute temporary path"),
        pytest.param("rm '{tmp}/tool'", id="a quoted absolute temporary path"),
    ],
)
def test_absolute_temporary_paths_pass_from_any_directory(project: Path, git_project: Path, command: str) -> None:
    command = command.format(tmp=project / "tmp")
    assert decide("allowed", command, cwd=git_project) == "allow"


@pytest.mark.parametrize(
    "command",
    [
        pytest.param('rm -f "{tmp}/link\\/sub"', id="a backslash the shell may drop"),
        pytest.param("rm -f {tmp}/a\\b", id="an escaped character"),
        pytest.param("rm {tmp}/'=tool'", id="a quoted equals sign"),
        pytest.param("rm {tmp}/=tool", id="an equals sign"),
        pytest.param("rm '{tmp}/a b'", id="a space"),
        pytest.param("rm '{tmp}/a;b'", id="a separator character"),
        pytest.param('rm "{tmp}/a\'b"', id="a quote character"),
        pytest.param("rm '{tmp}/{{a,b}}' \"{tmp}/[c]\" {tmp}/\\*", id="quoted or escaped glob and brace characters"),
    ],
)
def test_temporary_paths_with_characters_outside_the_plain_set_ask(project: Path, command: str) -> None:
    command = command.format(tmp=project / "tmp")
    assert decide("allowed", command) == "ask"
    assert decide("forbidden", command) == "allow"


def test_a_recursive_removal_through_a_dropped_backslash_stays_denied(project: Path) -> None:
    assert decide("forbidden", f'rm -rf "{project / "tmp"}/link\\/sub"') == "deny"


@pytest.mark.parametrize("root", ["scratch", "tmp"])
def test_a_temporary_root_that_links_outside_the_system_temp_areas_is_not_a_root(
    project: Path, monkeypatch: pytest.MonkeyPatch, root: str
) -> None:
    link = project / f"{root}-link"
    link.symlink_to("/usr")
    if root == "scratch":
        monkeypatch.setattr(guard.removal_policy, "SCRATCH_ROOT", link)
    else:
        monkeypatch.setenv("TMPDIR", str(link))
    assert decide("allowed", f"rm {link}/never-created.txt") == "ask"
    assert decide("forbidden", f"rm -rf {link}/never-created") == "deny"


def test_a_reassigned_home_cannot_vouch_for_a_target(
    project: Path, git_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(git_project))
    assert decide("allowed", f"HOME={git_project.parent}; rm ~/tracked.txt") == "ask"


def test_a_symlink_out_of_the_temporary_directory_does_not_count_as_temporary(
    project: Path, git_project: Path
) -> None:
    link = project / "tmp/link"
    link.symlink_to(git_project)
    assert decide("forbidden", f"rm -rf {link}/") == "deny"


@pytest.mark.parametrize("name", ["[t]racked.txt", "tracked*.txt", ":(top)tracked.txt"])
def test_untracked_names_that_git_would_read_as_patterns_ask(project: Path, git_project: Path, name: str) -> None:
    (git_project / name).write_text("untracked")
    assert decide("allowed", f"rm '{name}'") == "ask"


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_tracked_files_whose_changes_git_skips_ask(project: Path, git_project: Path, flag: str) -> None:
    git(git_project, "update-index", flag, "tracked.txt")
    (git_project / "tracked.txt").write_text("uncommitted")
    assert decide("allowed", "rm tracked.txt") == "ask"


def test_a_flagged_file_without_changes_still_asks(project: Path, git_project: Path) -> None:
    git(git_project, "update-index", "--assume-unchanged", "tracked.txt")
    assert decide("allowed", "rm tracked.txt") == "ask"


def test_a_clean_filter_cannot_hide_uncommitted_content(project: Path, git_project: Path) -> None:
    git(git_project, "config", "filter.keep-head.clean", "head -c 6")
    (git_project / ".git/info/attributes").write_text("tracked.txt filter=keep-head\n")
    (git_project / "tracked.txt").write_text("before and uncommitted notes")
    assert decide("allowed", "rm tracked.txt") == "ask"
