"""A session may drive only the Herdr agents it started; other panes may be the user's."""

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
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    store.register(root, "codex", "session")
    return root


@pytest.fixture
def herdr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake Herdr whose live agent names come from a file the test controls."""
    directory = tmp_path / "bin"
    directory.mkdir()
    names = tmp_path / "live_agents.txt"
    names.write_text("")
    script = directory / "herdr"
    workspaces = tmp_path / "workspaces.json"
    workspaces.write_text('{"result":{"workspaces":[]}}')
    script.write_text(
        "#!/bin/sh\n"
        f'if [ "$1 $2" = "workspace list" ]; then cat {workspaces}; exit 0; fi\n'
        f'agents=$(sed -E \'s/^([^ ]*) ?(.*)$/{{"name":"\\1","workspace_id":"\\2"}}/\' {names} | paste -sd, -)\n'
        'printf \'{"result":{"agents":[%s]}}\\n\' "$agents"\n'
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return names


def run(repository: Path, command: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(hook), "codex", "pre-tool-use"],
        input=json.dumps(
            {"cwd": str(repository), "session_id": "session", "tool_name": "Bash", "tool_input": {"command": command}}
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return json.loads(result.stdout)


def decision(output: dict) -> str:
    return output.get("hookSpecificOutput", {}).get("permissionDecision", "allow")


def test_a_session_prompts_the_agent_it_started(repository: Path, herdr: Path) -> None:
    assert decision(run(repository, "herdr agent start lane-a --kind claude --pane w1:p2")) == "allow"
    assert decision(run(repository, "herdr agent prompt lane-a 'Implement #181' --wait")) == "allow"


@pytest.mark.parametrize(
    "target", ["reviewer", "w1:p2", "$AGENT"], ids=["another name", "a pane id", "a run-time target"]
)
def test_prompting_an_agent_the_session_did_not_start_asks(repository: Path, herdr: Path, target: str) -> None:
    run(repository, "herdr agent start lane-a --kind claude --pane w1:p2")
    output = run(repository, f"herdr agent prompt {target} 'rm -rf ~'")
    assert decision(output) == "ask"
    assert "not started by this session" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_name_another_agent_already_holds_is_not_claimed(repository: Path, herdr: Path) -> None:
    herdr.write_text("reviewer\n")
    assert decision(run(repository, "herdr agent start reviewer --kind claude --pane w1:p2")) == "ask"
    herdr.write_text("")
    assert decision(run(repository, "herdr agent prompt reviewer 'hello'")) == "ask"


def test_ownership_belongs_to_one_session(repository: Path, herdr: Path) -> None:
    run(repository, "herdr agent start lane-a --kind claude --pane w1:p2")
    store.register(repository, "codex", "other")
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(hook), "codex", "pre-tool-use"],
        input=json.dumps(
            {
                "cwd": str(repository),
                "session_id": "other",
                "tool_name": "Bash",
                "tool_input": {"command": "herdr agent prompt lane-a 'hello'"},
            }
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert decision(json.loads(result.stdout)) == "ask"


def test_renaming_asks_so_an_owned_name_cannot_move_to_another_pane(repository: Path, herdr: Path) -> None:
    run(repository, "herdr agent start lane-a --kind claude --pane w1:p2")
    assert decision(run(repository, "herdr agent rename w1:p9 lane-a")) == "ask"


@pytest.mark.parametrize("command", ["herdr agent list", "herdr pane list", "echo herdr agent prompt reviewer"])
def test_other_herdr_commands_are_not_the_ownership_checks_concern(
    repository: Path, herdr: Path, command: str
) -> None:
    assert decision(run(repository, command)) == "allow"


@pytest.mark.parametrize("command", ["herdr workspace close w9", "herdr worktree remove --workspace w9"])
def test_a_session_closes_the_workspace_its_lane_ran_in(repository: Path, herdr: Path, command: str) -> None:
    run(repository, "herdr agent start lane-a --kind claude --pane w9:p1")
    herdr.write_text("lane-a w9\n")
    assert decision(run(repository, command)) == "allow"


@pytest.mark.parametrize(
    "agents", ["reviewer w9\n", "lane-a w9\n w9\n", ""], ids=["another agent", "an unnamed agent", "no agent"]
)
def test_closing_a_workspace_with_other_or_no_agents_asks(repository: Path, herdr: Path, agents: str) -> None:
    run(repository, "herdr agent start lane-a --kind claude --pane w9:p1")
    herdr.write_text(agents)
    assert decision(run(repository, "herdr workspace close w9")) == "ask"


def open_workspaces(tmp_path: Path, *entries: tuple[str, str]) -> None:
    rows = [
        {"workspace_id": ws, "worktree": {"checkout_path": path, "is_linked_worktree": False}} for ws, path in entries
    ]
    (tmp_path / "workspaces.json").write_text(json.dumps({"result": {"workspaces": rows}}))


def test_the_parent_workspace_a_worktree_opened_closes_with_the_lane(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    run(repository, "herdr worktree create --cwd /repos/site --branch feat/x --no-focus")
    open_workspaces(tmp_path, ("w5", "/repos/site"))
    assert decision(run(repository, "herdr workspace close w5")) == "allow"


def test_a_parent_workspace_the_user_already_had_open_is_left_alone(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    open_workspaces(tmp_path, ("w5", "/repos/site"))
    run(repository, "herdr worktree create --cwd /repos/site --branch feat/x --no-focus")
    assert decision(run(repository, "herdr workspace close w5")) == "ask"


def test_a_recorded_parent_with_an_agent_in_it_asks(repository: Path, herdr: Path, tmp_path: Path) -> None:
    run(repository, "herdr worktree create --cwd /repos/site --branch feat/x --no-focus")
    open_workspaces(tmp_path, ("w5", "/repos/site"))
    herdr.write_text(" w5\n")
    assert decision(run(repository, "herdr workspace close w5")) == "ask"
