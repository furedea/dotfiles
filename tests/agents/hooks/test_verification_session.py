import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT


hook = REPO_ROOT / "agents/hooks/verification_session.py"
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
        [sys.executable, "-I", "-B", str(hook), "codex", event],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_missing_registration_denies_tools_mechanically(repository: Path) -> None:
    result = invoke("pre", {"cwd": str(repository), "session_id": "session", "tool_name": "Bash"})
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "SessionStart" in result.stdout


def test_registered_session_allows_tools_without_launch_environment(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = store.register(repository, "codex", "session")
    result = invoke("pre", {"cwd": str(repository), "session_id": "session", "tool_name": "Bash"})
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}
    assert run.results()["session_id"] == "session"


@pytest.mark.parametrize("filename, field, value", [("baseline.json", "files", []), ("results.json", "checks", [])])
def test_corrupt_registration_denies_tools(repository: Path, filename: str, field: str, value: object) -> None:
    run = store.register(repository, "codex", "session")
    path = run.directory / filename
    record = json.loads(path.read_text())
    record[field] = value
    path.write_text(json.dumps(record))
    result = invoke("pre", {"cwd": str(repository), "session_id": "session"})
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_busy_registration_denies_tools_without_waiting_for_hook_timeout(repository: Path) -> None:
    run = store.register(repository, "codex", "session")
    with run.lock():
        result = invoke("pre", {"cwd": str(repository), "session_id": "session"})
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


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
    store.register(repository, "codex", "session")
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
    store.register(repository, "codex", "session")
    other = tmp_path / "other"
    subprocess.run(["git", "init", "--quiet", str(other)], check=True)
    result = invoke("pre", {"cwd": str(other), "session_id": "session", "tool_name": "Bash"})
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_stop_without_registration_reports_unresolved_and_does_not_loop(repository: Path) -> None:
    first = invoke("stop", {"cwd": str(repository), "session_id": "session"})
    assert json.loads(first.stdout)["decision"] == "block"
    repeated = invoke("stop", {"cwd": str(repository), "session_id": "session", "stop_hook_active": True})
    assert "unresolved" in json.loads(repeated.stdout)["systemMessage"]


def test_failed_baseline_leaves_tools_denied(repository: Path, tmp_path: Path) -> None:
    (repository / "external").symlink_to(tmp_path)
    payload = {"cwd": str(repository), "session_id": "session", "source": "startup"}
    assert "outside" in json.loads(invoke("start", payload).stdout)["systemMessage"]
    assert json.loads(invoke("pre", payload).stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.integration
@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_generated_hooks_register_and_verify_without_a_launcher(
    provider: str, tmp_path: Path, repository: Path
) -> None:
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
    payload = {"cwd": str(repository), "session_id": "session", "source": "startup"}
    for event, action in (("SessionStart", "start"), ("PreToolUse", "pre"), ("Stop", "stop"), ("SessionEnd", "end")):
        handlers = [hook for group in events.get(event, []) for hook in group["hooks"]]
        handler = next(
            hook for hook in handlers if hook["command"].endswith(f'verification_session.py" {provider} {action}')
        )
        assert handler.get("async", False) is False
        result = subprocess.run(
            handler["command"],
            shell=True,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        assert "decision" not in output
        assert output == {} or "no changes" in output.get("systemMessage", "")
    run = store.load(store.session_directory(repository, provider, "session"))
    assert run.results()["ended_at"] > 0
    installed = prefix / ".claude/hooks/verification_session.py"
    assert os.access(installed, os.X_OK)
    result = subprocess.run(
        [
            str(installed),
            provider,
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
    run = store.register(repository, "codex", "old-session")
    (repository / "source.py").write_text("pending edit")
    result = invoke("start", {"cwd": str(repository), "session_id": "new-session", "source": "clear"})
    assert json.loads(result.stdout) == {}
    assert run.baseline.changed_paths(store.capture(repository)) == ("source.py",)
    cleared = store.load(store.session_directory(repository, "codex", "new-session"))
    assert cleared.results()["revalidate_all"] is True


def test_explicit_check_uses_registered_context_without_reading_stdin(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = store.register(repository, "codex", "session")
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(hook), "check", str(run.directory)],
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
    run = store.register(repository, "codex", "session")
    (repository / "source.sh").write_text("changed")
    (repository / "tests").mkdir()
    (repository / "tests/source.bats").write_text("test")
    runner = tmp_path / "bats"
    runner.write_text("#!/bin/sh\nprintf '1..1\\nnot ok 1 failure\\n'\nexit 1\n")
    runner.chmod(0o755)
    monkeypatch.setenv("RUN_RELATED_TESTS_BATS_BIN", str(runner))
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(hook), "check", str(run.directory)],
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
    store.register(repository, "codex", "session")
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
    store.register(repository, "codex", "session")
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
