"""Cleanup may run unreviewed only as one of its two documented calls."""

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
pytestmark = pytest.mark.usefixtures("isolated_project")


@pytest.mark.parametrize("suffix", ["", " --dry-run"])
def test_cleanup_documented_calls_are_allowed(suffix: str) -> None:
    command = "/Users/kaito/.claude/hooks/cleanup_worktrees.py" + suffix
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "allow"


@pytest.mark.parametrize("suffix", ["", " --dry-run"])
def test_cleanup_tilde_calls_require_review(suffix: str) -> None:
    command = "~/.claude/hooks/cleanup_worktrees.py" + suffix
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize(
    "path", ["/Users/kaito/.claude/hooks/cleanup_worktrees.py", "~/.claude/hooks/cleanup_worktrees.py"]
)
@pytest.mark.parametrize(
    "shape",
    [
        "{path} --help",
        "{path} --force",
        "{path} extra",
        "{path} --dry-run extra",
        "{path} --dry-run --dry-run",
        "{path} '--dry-run'",
        "{path} && true",
        "true; {path}",
        "{path}\ntrue",
        "{path} | cat",
        "{path} > out.txt",
        "{path} 2>&1",
        "{path} &",
        "({path})",
        "X=1 {path}",
        "env {path}",
        "command {path}",
        "python3 {path}",
        "{path} $FLAGS",
        "{path} $(printf -- --force)",
    ],
)
def test_cleanup_other_arguments_and_shell_shapes_require_review(path: str, shape: str) -> None:
    assert guard.decide("allowed", {"tool_input": {"command": shape.format(path=path)}}).decision != "allow"


@pytest.mark.parametrize(
    "command", ["/tmp/cleanup_worktrees.py", "cleanup_worktrees.py", "$HOME/.claude/hooks/cleanup_worktrees.py"]
)
def test_cleanup_other_program_paths_require_review(command: str) -> None:
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision != "allow"


@pytest.mark.parametrize("separator", ["\n", "\r"])
@pytest.mark.parametrize("shape", ["{path}{separator}--dry-run", "{path} --dry-run{separator}"])
def test_cleanup_line_breaks_require_review(separator: str, shape: str) -> None:
    command = shape.format(path="/Users/kaito/.claude/hooks/cleanup_worktrees.py", separator=separator)
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"


@pytest.mark.parametrize(
    "wrapper", ["python", "python3", "python3.13", "/usr/bin/python3.13", "uv run", "bash", "sh", "zsh"]
)
@pytest.mark.parametrize("suffix", ["", " --dry-run", " --force"])
def test_cleanup_wrapped_calls_require_review(wrapper: str, suffix: str) -> None:
    command = f"{wrapper} /Users/kaito/.claude/hooks/cleanup_worktrees.py{suffix}"
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"
