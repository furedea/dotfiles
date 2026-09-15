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
        ("git", "restore", "--staged", "--worktree", "file.py"),
        ("gh", "pr", "merge", "--admin"),
    ],
)
def test_destructive_operations_are_rejected(arguments: tuple[str, ...]) -> None:
    assert git.reason(arguments)


@pytest.mark.parametrize(
    "arguments", [("git", "status"), ("git", "restore", "--staged", "file.py"), ("git", "push", "origin", "topic")]
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
