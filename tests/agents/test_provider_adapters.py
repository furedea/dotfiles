"""Behavior every provider hook adapter shares, exercised through each real entry point."""

import json
from pathlib import Path
import shutil

import pytest

from tests.runtime import CliRunner, REPO_ROOT, load_script_module


PROVIDERS = ("codex", "devin", "hermes", "pi")


def script(provider: str) -> str:
    return f"agents/{provider}/hooks/hook_adapter.py"


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    root = tmp_path / "harness"
    home.mkdir()
    rules = root / ".claude/hooks/rules"
    rules.mkdir(parents=True)
    paths = [f"~/.{provider}/hooks/hook_adapter.py" for provider in PROVIDERS]
    (rules / "protected_paths.json").write_text(json.dumps({"version": 1, "paths": paths}))
    shutil.copyfile(REPO_ROOT / "agents/hooks/rules/secret_path_policy.json", rules / "secret_path_policy.json")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_HARNESS_ROOT", str(root))
    for name in ("AGENT_PROTECTED_PATH_POLICY", "AGENT_SECRET_PATH_POLICY", "DEVIN_PROJECT_DIR"):
        monkeypatch.delenv(name, raising=False)
    return root


@pytest.fixture
def state(isolated_project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Audit logging refuses a state directory inside the working tree it describes.
    path = isolated_project.parent / (isolated_project.name + "-state")
    monkeypatch.setenv("XDG_STATE_HOME", str(path))
    return path


def audit_rows(state: Path) -> list[dict]:
    logs = sorted((state / "agent-harness/audit").rglob("*.jsonl"))
    return [json.loads(line) for path in logs for line in path.read_text().splitlines()]


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(
    "case",
    [("command", {"command": "cat .env"}), ("patch", {"file_path": "~/.ssh/config"})],
)
def test_secret_path_denial_is_audited_for_the_provider(
    run_cli: CliRunner, harness: Path, state: Path, provider: str, case: tuple[str, dict]
) -> None:
    mode, values = case
    payload = {"session_id": "adapter-session", "tool_input": values}
    result = run_cli(script(provider), "paths", mode, payload=payload)
    assert result.returncode == 2
    [row] = audit_rows(state)
    assert row["status"] == "blocked"
    assert row["provider"] == provider
    assert row["rule"] == "guard_secret_paths.sh"


@pytest.mark.parametrize("provider", ["devin", "pi"])
def test_notebook_edits_are_checked_against_the_harness_boundary(
    run_cli: CliRunner, harness: Path, provider: str
) -> None:
    values = {"notebook_path": f"~/.{provider}/hooks/hook_adapter.py", "new_source": "x = 1"}
    result = run_cli(script(provider), "harness", payload={"tool_name": "notebook_edit", "tool_input": values})
    assert result.returncode == 2
    assert "agent harness boundary" in result.stderr


SESSION_START = {"devin": "SessionStart", "hermes": "on_session_start"}


@pytest.mark.parametrize("provider", sorted(SESSION_START))
@pytest.mark.parametrize("source,recorded", [("startup", False), ("", False), ("compact", True), ("resume", True)])
def test_session_start_compaction_is_recorded_only_for_compact_or_resume(
    run_cli: CliRunner, state: Path, provider: str, source: str, recorded: bool
) -> None:
    payload = {"hook_event_name": SESSION_START[provider], "session_id": "adapter-session", "source": source}
    result = run_cli(script(provider), "audit", "compaction", payload=payload)
    assert result.returncode == 0
    rows = audit_rows(state)
    assert len(rows) == int(recorded)
    if recorded:
        assert rows[0]["event"] == "SessionStart"
        assert rows[0]["source"] == source
        assert rows[0]["provider"] == provider


@pytest.mark.parametrize(
    "provider,event,expected",
    [
        ("devin", "PostCompaction", "PostCompaction"),
        ("pi", "session_before_compact", "PreCompact"),
        ("pi", "session_compact", "PostCompaction"),
        ("devin", "", None),
    ],
)
def test_native_compaction_events_are_recorded_under_the_shared_name(
    run_cli: CliRunner, state: Path, provider: str, event: str, expected: str | None
) -> None:
    payload = {"hook_event_name": event, "session_id": "adapter-session"}
    result = run_cli(script(provider), "audit", "compaction", payload=payload)
    assert result.returncode == 0
    assert [row["event"] for row in audit_rows(state)] == ([expected] if expected else [])


@pytest.mark.parametrize("provider", PROVIDERS)
def test_normalization_leaves_the_provider_payload_untouched(provider: str) -> None:
    adapter = load_script_module(script(provider), f"{provider}_hook_adapter_under_test").ADAPTER
    payload = {"tool_name": "write", "tool_input": {"path": "notes.txt"}, "args": {"path": "other.txt"}}
    original = json.loads(json.dumps(payload))
    adapter.normalized(payload)
    assert payload == original


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("raw", ["{", "null", "[]"])
def test_non_object_payloads_are_rejected(run_cli: CliRunner, harness: Path, provider: str, raw: str) -> None:
    result = run_cli(script(provider), "shell", "git", payload=raw)
    assert result.returncode == 2
    assert "BLOCKED" in result.stderr
