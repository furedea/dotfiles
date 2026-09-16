"""Git safety contracts inspect text without executing the submitted commands."""

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_git.py", "guard_git")
pytestmark = pytest.mark.usefixtures("isolated_project")


@pytest.mark.parametrize(
    "command,status,fragments",
    [
        pytest.param(
            'echo "$(git reset --hard)"',
            2,
            ["BLOCKED"],
            id="blocks command substitution that cannot be statically approved",
        ),
        pytest.param("git push origin feature/foo", 0, [], id="allows push to feature branch"),
        pytest.param(
            "git push -u origin feature/foo",
            0,
            [],
            id="allows -u origin feature/foo (boolean -u, does not consume origin)",
        ),
        pytest.param(
            "git push --set-upstream origin feature/bar",
            0,
            [],
            id="allows --set-upstream origin feature/bar (boolean --set-upstream)",
        ),
        pytest.param("git pull origin main", 0, [], id="allows git pull (not governed)"),
        pytest.param("gh pr merge 42 --squash", 0, [], id="allows gh pr merge without --admin"),
        pytest.param("gh pr merge 42 --rebase", 0, [], id="allows gh pr merge with rebase"),
        pytest.param("ls -la", 0, [], id="passes through ls"),
        pytest.param("git status", 0, [], id="passes through git status"),
        pytest.param("git push --force origin feature/foo", 2, ["force-push flag"], id="blocks --force"),
        pytest.param("git push -f origin feature/foo", 2, [], id="blocks -f short flag"),
        pytest.param(
            "env git push --force origin feature/foo", 2, ["wrapper"], id="blocks env wrapper around --force"
        ),
        pytest.param(
            "/usr/bin/time -p git push --force origin feature/foo", 2, [], id="blocks time wrapper around --force"
        ),
        pytest.param("time git push --force origin feature/foo", 2, [], id="blocks time keyword around --force"),
        pytest.param(
            "timeout 30 git push --force origin feature/foo", 2, [], id="blocks timeout wrapper around --force"
        ),
        pytest.param(
            "echo feature/foo | xargs git push --force origin", 2, [], id="blocks xargs wrapper around --force"
        ),
        pytest.param("exec git push --force origin feature/foo", 2, [], id="blocks exec wrapper around --force"),
        pytest.param("nohup git push --force origin feature/foo", 2, [], id="blocks nohup wrapper around --force"),
        pytest.param("nice -n 5 git push --force origin feature/foo", 2, [], id="blocks nice wrapper around --force"),
        pytest.param("env -u XDG_CONFIG_HOME git status", 0, [], id="allows env wrapper around a read-only command"),
        pytest.param("command -v git", 0, [], id="allows command lookups"),
        pytest.param("git push --force-with-lease origin feature/foo", 2, [], id="blocks --force-with-lease"),
        pytest.param(
            "git push --force-with-lease=origin/foo origin feature/foo",
            2,
            [],
            id="blocks --force-with-lease with value",
        ),
        pytest.param("git push origin +feature/foo", 2, ["refspec"], id="blocks +refspec"),
        pytest.param("git push origin +feature/foo:main", 2, [], id="blocks +src:dst refspec"),
        pytest.param("git push origin main", 2, ["main"], id="blocks explicit origin main"),
        pytest.param("git push origin master", 2, ["master"], id="blocks explicit origin master"),
        pytest.param("git push origin HEAD:main", 2, [], id="blocks HEAD:main refspec"),
        pytest.param("git push origin HEAD:refs/heads/main", 2, [], id="blocks HEAD:refs/heads/main refspec"),
        pytest.param("git push origin feature/foo:main", 2, [], id="blocks src:main refspec"),
        pytest.param(
            "git push origin refs/heads/feature/foo:refs/heads/main", 2, [], id="blocks src:refs/heads/main refspec"
        ),
        pytest.param("git push -u origin feature/foo main", 2, [], id="blocks multi-refspec with main included"),
        pytest.param("gh pr merge 42 --admin", 2, ["admin"], id="blocks gh pr merge --admin (trailing)"),
        pytest.param("gh pr merge --admin 42", 2, [], id="blocks gh pr merge with --admin in middle"),
        pytest.param("cd /tmp && git push origin main", 2, [], id="blocks push to main after cd (&&)"),
        pytest.param("foo | git push --force origin feature/foo", 2, [], id="blocks --force in piped segment"),
        pytest.param("git status; git push origin main", 2, [], id="blocks push to main after semicolon"),
        pytest.param("ls | cat", 0, [], id="allows pipe with no destructive segment"),
        pytest.param('bash -c "git push --force origin main"', 2, ["wrapper"], id="blocks bash -c with --force"),
        pytest.param('sh -c "git push origin main"', 2, [], id="blocks sh -c with main push"),
        pytest.param('/bin/bash -c "git push --force"', 2, [], id="blocks /bin/bash -c with --force"),
        pytest.param('eval "git push --force origin main"', 2, [], id="blocks eval with --force"),
        pytest.param('zsh -c "gh pr merge 42 --admin"', 2, [], id="blocks zsh -c with admin merge"),
        pytest.param('bash -c "ls -la"', 0, [], id="allows bash -c with ls"),
        pytest.param(
            "git push --force origin feature/foo",
            2,
            ["Segment:", "git push --force origin feature/foo"],
            id="blocked force-push message includes the offending segment",
        ),
        pytest.param("git rm foo.py", 2, [], id="blocks git rm"),
        pytest.param("git rm --cached foo.py", 2, [], id="blocks git rm --cached"),
        pytest.param("git rm -r dir/", 2, [], id="blocks git rm -r"),
        pytest.param("git clean -fd", 2, [], id="blocks git clean -fd"),
        pytest.param("git clean -n", 2, [], id="blocks git clean -n (dry-run also blocked for symmetry)"),
        pytest.param("git stash drop", 2, [], id="blocks git stash drop"),
        pytest.param("git stash clear", 2, [], id="blocks git stash clear"),
        pytest.param("git branch -D feature/foo", 2, [], id="blocks git branch -D"),
        pytest.param("git branch -d feature/foo", 0, [], id="allows git branch -d (safe delete)"),
        pytest.param("git worktree remove ../foo", 2, [], id="blocks git worktree remove"),
        pytest.param("git worktree prune", 2, [], id="blocks git worktree prune"),
        pytest.param("git worktree move ../old ../new", 2, [], id="blocks git worktree move"),
        pytest.param("git worktree repair", 2, [], id="blocks git worktree repair"),
        pytest.param("git worktree list", 0, [], id="allows git worktree list"),
        pytest.param("git filter-branch --env-filter foo HEAD", 2, [], id="blocks git filter-branch"),
        pytest.param("git filter-repo --invert-paths --path foo", 2, [], id="blocks git filter-repo"),
        pytest.param("git replace abc def", 2, [], id="blocks git replace"),
        pytest.param("git reflog delete refs/heads/foo@{0}", 2, [], id="blocks git reflog delete"),
        pytest.param("git reflog expire --expire=now --all", 2, [], id="blocks git reflog expire"),
        pytest.param("git reflog", 0, [], id="allows git reflog (default subcommand show)"),
        pytest.param("git symbolic-ref --delete HEAD", 2, [], id="blocks git symbolic-ref --delete HEAD"),
        pytest.param("git symbolic-ref -d HEAD", 2, [], id="blocks git symbolic-ref -d HEAD"),
        pytest.param("git symbolic-ref HEAD", 0, [], id="allows git symbolic-ref HEAD (read)"),
        pytest.param("git gc --prune=now", 2, [], id="blocks git gc --prune=now"),
        pytest.param("git gc --prune now", 2, [], id="blocks git gc --prune now (separate token)"),
        pytest.param("git gc", 0, [], id="allows plain git gc"),
        pytest.param("git reset --hard HEAD", 2, [], id="blocks git reset --hard"),
        pytest.param("git reset HEAD~1 --hard", 2, [], id="blocks git reset HEAD~1 --hard (flag at end)"),
        pytest.param("git reset --keep HEAD~1", 2, [], id="blocks git reset --keep"),
        pytest.param("git reset --merge", 2, [], id="blocks git reset --merge"),
        pytest.param("git reset --soft HEAD~1", 0, [], id="allows git reset --soft"),
        pytest.param("git reset --mixed HEAD~1", 0, [], id="allows git reset --mixed"),
        pytest.param("git reset HEAD foo.py", 0, [], id="allows git reset HEAD <file> (default --mixed unstage)"),
        pytest.param("git checkout -- foo.py", 2, [], id="blocks git checkout -- foo.py"),
        pytest.param("git checkout .", 2, [], id="blocks git checkout ."),
        pytest.param("git checkout -f main", 2, [], id="blocks git checkout -f main"),
        pytest.param("git checkout --force main", 2, [], id="blocks git checkout --force main"),
        pytest.param("git checkout -B existing", 2, [], id="blocks git checkout -B existing"),
        pytest.param("git checkout main", 0, [], id="allows plain git checkout main"),
        pytest.param("git checkout -b new", 0, [], id="allows git checkout -b new"),
        pytest.param("git restore foo.py", 2, [], id="blocks git restore foo.py"),
        pytest.param("git restore --staged foo.py", 0, [], id="allows git restore --staged foo.py"),
        pytest.param(
            "git restore --staged --worktree foo.py", 2, [], id="blocks git restore --staged --worktree foo.py"
        ),
        pytest.param("git restore --source HEAD~1 foo.py", 2, [], id="blocks git restore --source HEAD~1 foo.py"),
        pytest.param("git switch --discard-changes main", 2, [], id="blocks git switch --discard-changes main"),
        pytest.param("git switch -f main", 2, [], id="blocks git switch -f main"),
        pytest.param("git switch --force main", 2, [], id="blocks git switch --force main"),
        pytest.param("git switch -C feature/foo", 2, [], id="blocks git switch -C feature/foo"),
        pytest.param("git switch main", 0, [], id="allows plain git switch"),
        pytest.param("git switch -c feature/foo", 0, [], id="allows git switch -c new"),
        pytest.param("git update-ref -d refs/heads/foo", 2, [], id="blocks git update-ref -d refs/heads/foo"),
        pytest.param(
            "git update-ref --no-deref -d refs/heads/foo",
            2,
            [],
            id="blocks git update-ref --no-deref -d refs/heads/foo (flag interleaved)",
        ),
        pytest.param(
            "git update-ref refs/heads/foo abc123",
            0,
            [],
            id="allows git update-ref refs/heads/foo SHA (non-delete write)",
        ),
        pytest.param('bash -c "git rm foo.py"', 2, [], id="blocks bash -c with git rm"),
        pytest.param("cd /tmp && git clean -fd", 2, [], id="blocks chained git clean"),
        pytest.param("git status; git reset --hard HEAD", 2, [], id="blocks chained git reset --hard"),
        pytest.param('bash -c "git update-ref -d refs/heads/foo"', 2, [], id="blocks bash -c with git update-ref -d"),
        pytest.param("cd /tmp && git checkout -- foo.py", 2, [], id="blocks chained git checkout -- after cd"),
        pytest.param("", 0, [], id="empty command"),
        pytest.param('bash -c "echo hello"', 0, [], id="benign wrapped echo"),
    ],
)
def test_dangerous_git_contract(
    capsys: pytest.CaptureFixture[str], command: str, status: int, fragments: list[str]
) -> None:
    assert guard.check({"tool_input": {"command": command}}) == status
    captured = capsys.readouterr()
    assert captured.out == ""
    for fragment in fragments:
        assert fragment in captured.err
