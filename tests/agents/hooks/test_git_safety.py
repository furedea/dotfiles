"""Dangerous Git flags are evaluated as arguments, not substrings of shell text."""

import pytest

from tests.runtime import load_script_module


git = load_script_module("agents/hooks/lib/git_safety.py", "git_safety")
syntax = load_script_module("agents/hooks/lib/shell_syntax.py", "shell_syntax")


@pytest.mark.parametrize(
    "arguments",
    [
        ("git", "reset", "HEAD~1", "--hard"),
        ("git", "restore", "file.py"),
        ("git", "push", "origin", "HEAD:main"),
        ("git", "push", "--force-with-lease=main", "origin", "topic"),
        ("git", "push", "--force-with-lease", "origin", "topic"),
        ("git", "push", "--force-with-lease", "--force-if-includes", "origin", "main"),
        ("git", "push", "--force", "--force-if-includes", "origin", "topic"),
        ("git", "restore", "--staged", "--worktree", "file.py"),
        ("git", "rm", "-f", "file.py"),
        ("git", "mv", "--force", "a.py", "b.py"),
        ("git", "worktree", "remove", "--force", "../topic"),
        ("gh", "pr", "merge", "--admin"),
    ],
)
def test_destructive_operations_are_rejected(arguments: tuple[str, ...]) -> None:
    assert git.reason(arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        ("git", "status"),
        ("git", "restore", "--staged", "file.py"),
        ("git", "push", "origin", "topic"),
        ("git", "push", "--force-with-lease", "--force-if-includes", "origin", "topic"),
        ("git", "rm", "--cached", "file.py"),
        ("git", "mv", "a.py", "b.py"),
        ("git", "worktree", "remove", "../topic"),
        ("git", "worktree", "prune"),
        ("git", "stash", "drop"),
    ],
)
def test_non_destructive_operations_remain_available(arguments: tuple[str, ...]) -> None:
    assert not git.reason(arguments)


def test_unicode_and_quotes_do_not_shift_command_boundaries() -> None:
    commands = syntax.parse('echo "日本語; unchanged"; git push origin "feature/topic"')
    assert commands[0].arguments == ("echo", "日本語; unchanged")
    assert commands[1].arguments == ("git", "push", "origin", "feature/topic")


@pytest.mark.parametrize(
    "command,inner",
    [
        ('echo "$(git reset --hard)"', ("git", "reset", "--hard")),
        ("echo <(git status)", ("git", "status")),
        ("echo `git status`", ("git", "status")),
        ("if true; then git status; fi", ("git", "status")),
        ("for f in $(ls); do echo done; done", ("ls",)),
        ("while true; do git status; done", ("git", "status")),
        ("cat <<EOF\n$(rm -rf build)\nEOF", ("rm", "-rf", "build")),
    ],
)
def test_commands_inside_substitutions_and_clauses_are_exposed(command: str, inner: tuple[str, ...]) -> None:
    assert inner in [parsed.arguments for parsed in syntax.parse(command)]


@pytest.mark.parametrize("command", ['echo "$(date)"', "echo $((1 + 1))", "echo <(git status)"])
def test_substituted_words_are_run_time_words(command: str) -> None:
    assert syntax.parse(command)[0].dynamic == (False, True)


def test_quoted_heredocs_are_standard_input() -> None:
    parsed = syntax.parse("python3 - <<'EOF' > out.txt\nprint('$HOME')\nEOF")[0]
    assert parsed.arguments == ("python3", "-")
    assert parsed.writes == ("out.txt",)
    assert parsed.words_text == "python3 -"


def test_a_heredoc_fed_to_a_shell_is_parsed_as_a_script() -> None:
    commands = syntax.parse("bash <<'EOF'\ngit reset --hard\nEOF")
    assert ("git", "reset", "--hard") in [parsed.arguments for parsed in commands]


@pytest.mark.parametrize("command", ["bash <<EOF\necho $X\nEOF", "echo $'\\x41'"])
def test_scripts_whose_text_is_computed_still_require_review(command: str) -> None:
    with pytest.raises(syntax.UnsupportedSyntax):
        syntax.parse(command)


@pytest.mark.parametrize(
    "command,arguments,dynamic",
    [
        ('git push origin "$TARGET"', ("git", "push", "origin", '"$TARGET"'), (False, False, False, True)),
        ("rg foo *.py", ("rg", "foo", "*.py"), (False, False, True)),
        ("cat ${HOME:-/tmp}/x", ("cat", "${HOME:-/tmp}/x"), (False, True)),
        ("cat ~tester/x", ("cat", "~tester/x"), (False, True)),
        ("$CMD --version", ("$CMD", "--version"), (True, False)),
        ("ls -la", ("ls", "-la"), (False, False)),
    ],
)
def test_run_time_words_are_reported_rather_than_refused(
    command: str, arguments: tuple[str, ...], dynamic: tuple[bool, ...]
) -> None:
    parsed = syntax.parse(command)[0]
    assert parsed.arguments == arguments
    assert parsed.dynamic == dynamic
    assert parsed.program_is_dynamic == dynamic[0]


def test_dynamic_flags_follow_arguments_through_wrappers() -> None:
    innermost = syntax.parse("env CI=1 rg foo *.py")[-1]
    assert innermost.arguments == ("rg", "foo", "*.py")
    assert innermost.dynamic == (False, False, True)


@pytest.mark.parametrize(
    "command,writes",
    [
        ("rg foo > out.txt", ("out.txt",)),
        ("rg foo >> log 2>&1", ("log",)),
        ("rg foo 2>/dev/null >/dev/null", ("/dev/null", "/dev/null")),
        ("rg foo 2>&1 | wc -l", ()),
        ("cat < input.txt", ()),
        ("rg foo &> all.txt", ("all.txt",)),
        ("rg foo >| clobber.txt", ("clobber.txt",)),
        ("rg foo >&2", ()),
    ],
)
def test_output_redirections_are_reported_as_writes(command: str, writes: tuple[str, ...]) -> None:
    assert syntax.parse(command)[0].writes == writes


def test_home_directory_expansions_are_resolved_statically(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/tester")
    command = syntax.parse('cat "$HOME/notes.txt" ~/todo.txt ~ ${HOME}/x')[0]
    assert command.arguments == (
        "cat",
        "/home/tester/notes.txt",
        "/home/tester/todo.txt",
        "/home/tester",
        "/home/tester/x",
    )
    assert command.raw == 'cat "$HOME/notes.txt" ~/todo.txt ~ ${HOME}/x'


def test_single_quoted_home_text_stays_literal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/tester")
    assert syntax.parse("printf '%s' '$HOME' '~'")[0].arguments == ("printf", "%s", "$HOME", "~")


@pytest.mark.parametrize(
    "command",
    ["cat ~tester/x", "cat $HOME_DIR/x", "cat ${HOME:-/tmp}/x", "cat ${#HOME}", "cat ${HOME}/$TARGET"],
)
def test_other_expansions_are_not_resolved(command: str) -> None:
    parsed = syntax.parse(command)[0]
    assert parsed.dynamic == (False, True)
    assert "/home/" not in parsed.arguments[1]


def test_literal_wrapper_commands_are_inspected_recursively() -> None:
    assert syntax.parse("bash -lc 'git status'")[-1].arguments == ("git", "status")


@pytest.mark.parametrize(
    "command,expected",
    [
        ("env BATS_TMPDIR=/tmp bats tests/x.bats", ("bats", "tests/x.bats")),
        ("env -u XDG_CONFIG_HOME -i git status", ("git", "status")),
        ("/usr/bin/time -p git push --force origin topic", ("git", "push", "--force", "origin", "topic")),
        ("time git status", ("git", "status")),
        ("timeout -k 5 30 git status", ("git", "status")),
        ("nice -n 10 cargo build", ("cargo", "build")),
        ("nohup cargo run", ("cargo", "run")),
        ("exec git status", ("git", "status")),
        ("caffeinate -i git status", ("git", "status")),
        ("echo x | xargs -0 -I {} git add {}", ("git", "add", "{}")),
        ("command git status", ("git", "status")),
        ("env FOO=1 bash -c 'git status'", ("git", "status")),
    ],
)
def test_process_wrappers_expose_the_command_they_run(command: str, expected: tuple[str, ...]) -> None:
    innermost = syntax.parse(command)[-1]
    assert innermost.arguments == expected
    assert innermost.raw == " ".join(expected)


def test_wrapped_commands_keep_their_redirections_and_depth() -> None:
    innermost = syntax.parse("env CI=1 cargo test > /tmp/blocked")[-1]
    assert innermost.raw == "cargo test > /tmp/blocked"
    assert innermost.redirections == ("/tmp/blocked",)
    assert innermost.wrapper_depth == 1


@pytest.mark.parametrize("command", ["command -v rg", "env", "env -i", "xargs"])
def test_wrapper_lookups_and_bare_invocations_are_not_unwrapped(command: str) -> None:
    commands = syntax.parse(command)
    assert len(commands) == 1
    assert commands[0].wrapper_depth == 0


def test_unknown_wrapper_options_are_not_silently_skipped() -> None:
    with pytest.raises(syntax.UnsupportedSyntax):
        syntax.parse("xargs --unknown-option git add .")


@pytest.mark.parametrize(
    "arguments,expected",
    [
        ((), ""),
        (("gh", "pr", "merge", "42", "--admin"), "gh pr merge --admin bypasses branch protection"),
        (("gh", "pr", "merge", "42"), ""),
        (("/usr/bin/rm", "-rf", "x"), ""),
        (("git",), ""),
        (("git", "-C", "/tmp"), ""),
        (("git", "commit", "-S", "-m", "x"), "agent commits and tags are unsigned"),
        (("git", "tag", "--local-user=me", "v1"), "agent commits and tags are unsigned"),
        (("git", "push", "-u", "origin", "topic"), "the sandbox cannot write .git/config"),
        (("git", "push", "--force", "origin", "topic"), "force-push flag detected"),
        (("git", "reset", "--hard"), "destructive git operation: reset"),
        (("git", "worktree", "move", "a", "b"), "destructive git operation: worktree"),
        (("git", "reflog", "expire"), "destructive git operation: reflog"),
        (("git", "reflog", "show"), ""),
        (("git", "restore", "--staged", "--source=HEAD", "f"), "destructive git operation: restore"),
        (("/usr/local/bin/git", "-c", "a=b", "restore", "-S", "f"), ""),
    ],
)
def test_each_reason_branch_keeps_its_verdict(arguments: tuple[str, ...], expected: str) -> None:
    actual = git.reason(arguments)
    assert actual.startswith(expected) if expected else actual == ""
