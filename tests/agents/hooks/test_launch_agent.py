from pathlib import Path

import pytest

from tests.runtime import load_script_module


launcher = load_script_module("agents/hooks/launch_agent.py", "launch_agent")


@pytest.mark.parametrize("arguments", [("-C", "target"), ("--cd=target",), ("-Ctarget",)])
def test_relative_worktree_is_resolved_before_provider_cwd_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: tuple[str, ...],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "target").mkdir()
    plan = launcher.plan("codex", arguments)
    assert plan.directory == tmp_path / "target"
    assert plan.arguments[-2:] == ("--cd", str(tmp_path / "target"))


def test_prompt_text_is_not_a_configuration_override() -> None:
    plan = launcher.plan("codex", ("Explain why hooks=false appears in this file",))
    assert not plan.utility


def test_print_prompt_is_not_treated_as_an_authentication_subcommand() -> None:
    assert not launcher.plan("claude", ("-p", "login")).utility


def test_exec_resume_keeps_resume_semantics() -> None:
    assert launcher.plan("codex", ("exec", "resume", "--last")).resuming


@pytest.mark.parametrize("arguments", [("--disable", "hooks"), ("-c", "features.hooks=false")])
def test_explicit_hook_disable_is_rejected(arguments: tuple[str, ...]) -> None:
    with pytest.raises(launcher.StateError, match="hooks"):
        launcher.plan("codex", arguments)


def test_enabling_hooks_explicitly_is_allowed() -> None:
    assert not launcher.plan("codex", ("--enable", "hooks")).utility
