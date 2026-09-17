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
    "command", ['echo "$(git reset --hard)"', 'git push origin "$TARGET"', "if true; then git status; fi"]
)
def test_unsupported_execution_or_expansion_is_not_automatically_approved(command: str) -> None:
    with pytest.raises(syntax.UnsupportedSyntax):
        syntax.parse(command)


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
