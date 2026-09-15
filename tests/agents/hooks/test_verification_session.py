import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT


hook = REPO_ROOT / "agents/hooks/verification_session.py"
launcher = REPO_ROOT / "agents/hooks/launch_agent.py"
sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
import session_store as store


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("AGENT_VERIFICATION_RUN", raising=False)
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    (root / "source.py").write_text("before")
    return root


def invoke(event: str, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-B", str(hook), event],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def test_missing_registration_denies_tools_mechanically(repository: Path) -> None:
    result = invoke("pre", {"cwd": str(repository), "session_id": "session", "tool_name": "Bash"})
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "launcher" in result.stdout


def test_registration_is_bound_before_tools_even_if_session_start_delivery_is_missing(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = store.register(repository, "codex")
    monkeypatch.setenv("AGENT_VERIFICATION_RUN", str(run.directory))
    result = invoke("pre", {"cwd": str(repository), "session_id": "session", "tool_name": "Bash"})
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}
    assert run.results()["session_id"] == "session"


@pytest.mark.parametrize(
    "tool_input",
    [
        {"file_path": "../other.py"},
        {"command": "*** Begin Patch\n*** Add File: ../other.py\n+outside\n*** End Patch"},
        {"workdir": "..", "command": "echo changed"},
    ],
)
def test_explicit_mutation_outside_registered_root_is_denied(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool_input: dict,
) -> None:
    run = store.register(repository, "codex")
    monkeypatch.setenv("AGENT_VERIFICATION_RUN", str(run.directory))
    result = invoke(
        "pre",
        {
            "cwd": str(repository),
            "session_id": "session",
            "tool_name": "Write",
            "tool_input": tool_input,
        },
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_different_worktree_cannot_reuse_registration(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = store.register(repository, "codex")
    monkeypatch.setenv("AGENT_VERIFICATION_RUN", str(run.directory))
    other = tmp_path / "other"
    subprocess.run(["git", "init", "--quiet", str(other)], check=True)
    result = invoke("pre", {"cwd": str(other), "session_id": "session", "tool_name": "Bash"})
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_stop_without_registration_reports_unresolved_and_does_not_loop(repository: Path) -> None:
    first = invoke("stop", {"cwd": str(repository), "session_id": "session"})
    assert json.loads(first.stdout)["decision"] == "block"
    repeated = invoke("stop", {"cwd": str(repository), "session_id": "session", "stop_hook_active": True})
    assert "unresolved" in json.loads(repeated.stdout)["systemMessage"]


def test_launcher_registers_target_before_executing_provider_and_preserves_exit_status(
    repository: Path,
    tmp_path: Path,
) -> None:
    provider = tmp_path / "provider"
    provider.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "run = pathlib.Path(os.environ['AGENT_VERIFICATION_RUN'])\n"
        "baseline = json.loads((run / 'baseline.json').read_text())\n"
        "assert baseline['root'] == str(pathlib.Path.cwd())\n"
        "assert 'source.py' in baseline['files']\n"
        "print('registered before launch')\n"
        "sys.exit(7)\n"
    )
    provider.chmod(0o755)
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(launcher), "codex", str(provider), "-C", str(repository)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 7, result.stderr
    assert "registered before launch" in result.stdout
    records = list(store.state_directory().glob("*/*/results.json"))
    assert len(records) == 1
    assert json.loads(records[0].read_text())["ended_at"] > 0


def test_failed_baseline_prevents_provider_start(repository: Path, tmp_path: Path) -> None:
    (repository / "external").symlink_to(tmp_path)
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(launcher), "codex", "/usr/bin/false"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "outside" in result.stderr


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_help_does_not_require_a_worktree_or_create_state(provider: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(launcher), provider, "/usr/bin/true", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


def test_native_worktree_creation_cannot_move_target_after_baseline(repository: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(launcher), "codex", "/usr/bin/true", "--worktree"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "worktree" in result.stderr


@pytest.mark.integration
@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_generated_hooks_enforce_the_full_lifecycle(provider: str, tmp_path: Path) -> None:
    prefix = tmp_path / "installed"
    subprocess.run(
        [
            "agent-harness",
            "--profile",
            "minimal",
            "install",
            "--source",
            str(REPO_ROOT / "agents"),
            "--prefix",
            str(prefix),
            "--runtime-root",
            str(prefix),
        ],
        check=True,
        capture_output=True,
    )
    filename = ".codex/hooks.json" if provider == "codex" else ".claude/settings.json"
    events = json.loads((prefix / filename).read_text())["hooks"]
    for event, action in (("SessionStart", "start"), ("PreToolUse", "pre"), ("Stop", "stop"), ("SessionEnd", "end")):
        commands = [hook["command"] for group in events.get(event, []) for hook in group["hooks"]]
        assert any(command.endswith(f'verification_session.py" {action}') for command in commands), event
    installed = prefix / ".claude/hooks/verification_session.py"
    assert os.access(installed, os.X_OK)
    result = subprocess.run(
        [
            str(installed),
            "pre",
        ],
        input="{}",
        capture_output=True,
        text=True,
        check=False,
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_clear_preserves_pending_changes_with_a_new_session_id(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = store.register(repository, "codex")
    run.bind("old-session", resuming=False)
    monkeypatch.setenv("AGENT_VERIFICATION_RUN", str(run.directory))
    (repository / "source.py").write_text("pending edit")
    result = invoke("start", {"cwd": str(repository), "session_id": "new-session", "source": "clear"})
    assert json.loads(result.stdout) == {}
    assert run.results()["session_id"] == "new-session"
    assert run.baseline.changed_paths(store.capture(repository)) == ("source.py",)


def test_explicit_check_uses_registered_context_without_reading_stdin(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = store.register(repository, "codex")
    run.bind("session", resuming=False)
    monkeypatch.setenv("AGENT_VERIFICATION_RUN", str(run.directory))
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(hook), "check"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert "no changes" in json.loads(result.stdout)["systemMessage"]


def test_explicit_check_exits_unsuccessfully_for_a_reused_failure(
    repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = store.register(repository, "codex")
    run.bind("session", resuming=False)
    monkeypatch.setenv("AGENT_VERIFICATION_RUN", str(run.directory))
    (repository / "source.sh").write_text("changed")
    (repository / "tests").mkdir()
    (repository / "tests/source.bats").write_text("test")
    runner = tmp_path / "bats"
    runner.write_text("#!/bin/sh\nprintf '1..1\\nnot ok 1 failure\\n'\nexit 1\n")
    runner.chmod(0o755)
    monkeypatch.setenv("RUN_RELATED_TESTS_BATS_BIN", str(runner))
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(hook), "check"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1, result.stdout
    assert "unresolved" in json.loads(result.stdout)["systemMessage"]


@pytest.mark.parametrize("command", ["printf '%s\\n' cd /tmp", "printf '%s\\n' git -C /tmp"])
def test_directory_words_in_command_arguments_are_not_treated_as_directory_changes(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    run = store.register(repository, "codex")
    monkeypatch.setenv("AGENT_VERIFICATION_RUN", str(run.directory))
    result = invoke(
        "pre",
        {
            "cwd": str(repository),
            "session_id": "session",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        },
    )
    assert json.loads(result.stdout) == {}


@pytest.mark.parametrize("command", ["cd ..", "git -C .. status", "bash -c 'cd ..'"])
def test_literal_shell_worktree_changes_are_denied(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    run = store.register(repository, "codex")
    monkeypatch.setenv("AGENT_VERIFICATION_RUN", str(run.directory))
    result = invoke(
        "pre",
        {
            "cwd": str(repository),
            "session_id": "session",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        },
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
