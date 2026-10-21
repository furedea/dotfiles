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
    worktrees = tmp_path / "worktrees.json"
    worktrees.write_text('{"result":{"worktrees":[]}}')
    script.write_text(
        "#!/bin/sh\n"
        f'if [ "$1 $2" = "workspace list" ]; then cat {workspaces}; exit 0; fi\n'
        f'if [ "$1 $2" = "worktree list" ]; then cat {worktrees}; exit 0; fi\n'
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


def test_a_session_prompts_the_sonnet_agent_it_started(repository: Path, herdr: Path) -> None:
    start = "herdr agent start lane-a --kind claude --pane w1:p2 -- --model sonnet --effort medium"
    assert decision(run(repository, start)) == "allow"
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


PRIMARY = "/repos/site"
CREATE = f"herdr workspace create --cwd {PRIMARY} --label site --no-focus"


def workspace_list(tmp_path: Path, *entries: tuple[str, str, str], linked: tuple[str, ...] = ()) -> None:
    """Open workspaces as (id, checkout path, label); linked ones belong to the primary's group."""
    rows = [
        {"workspace_id": ws, "label": label, "worktree": {"checkout_path": path, "is_linked_worktree": False}}
        for ws, path, label in entries
    ] + [
        {"workspace_id": ws, "label": ws, "worktree": {"checkout_path": f"/lanes/{ws}", "is_linked_worktree": True}}
        for ws in linked
    ]
    (tmp_path / "workspaces.json").write_text(json.dumps({"result": {"workspaces": rows}}))
    group = [{"path": f"/lanes/{ws}", "open_workspace_id": ws} for ws in linked]
    (tmp_path / "worktrees.json").write_text(json.dumps({"result": {"worktrees": group}}))


def created(workspace: str = "w5", label: str = "site", cwd: str = PRIMARY) -> str:
    """The shape `herdr workspace create` returns: no checkout path, the directory is the root pane's."""
    result = {"workspace": {"workspace_id": workspace, "label": label}, "root_pane": {"pane_id": "p1", "cwd": cwd}}
    return json.dumps({"result": result})


def after(repository: Path, command: str, response: object) -> None:
    subprocess.run(
        [sys.executable, "-I", "-B", str(hook), "codex", "post-tool-use"],
        input=json.dumps(
            {
                "cwd": str(repository),
                "session_id": "session",
                "tool_name": "Bash",
                "tool_input": {"command": command},
                "tool_response": response,
            }
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )


def open_primary(repository: Path, tmp_path: Path, *, linked: tuple[str, ...] = ()) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"), linked=linked)
    run(repository, CREATE)
    after(repository, CREATE, {"stdout": created()})


GROUP_CLOSE = "herdr workspace close w5 --group"


def test_the_primary_this_session_created_closes_with_its_group(repository: Path, herdr: Path, tmp_path: Path) -> None:
    open_primary(repository, tmp_path, linked=("w6",))
    run(repository, "herdr agent start lane-a --kind claude --pane w6:p1")
    herdr.write_text("lane-a w6\n")
    assert decision(run(repository, GROUP_CLOSE)) == "allow"
    assert decision(run(repository, "herdr workspace close --group w5")) == "ask"


def test_the_group_close_accepts_the_group_option_first(repository: Path, herdr: Path, tmp_path: Path) -> None:
    open_primary(repository, tmp_path)
    assert decision(run(repository, "herdr workspace close --group w5")) == "allow"


def test_a_group_close_of_a_primary_the_user_already_had_asks(repository: Path, herdr: Path, tmp_path: Path) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    assert decision(run(repository, GROUP_CLOSE)) == "ask"


def test_a_group_with_another_agent_asks(repository: Path, herdr: Path, tmp_path: Path) -> None:
    open_primary(repository, tmp_path, linked=("w6",))
    herdr.write_text("reviewer w6\n")
    assert decision(run(repository, GROUP_CLOSE)) == "ask"


@pytest.mark.parametrize(
    "response", [{"stdout": "Error: failed"}, {"stdout": created(), "interrupted": True}, "", None]
)
def test_a_failed_create_owns_nothing(repository: Path, herdr: Path, tmp_path: Path, response: object) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, CREATE)
    after(repository, CREATE, response)
    assert decision(run(repository, GROUP_CLOSE)) == "ask"


def test_a_workspace_the_result_does_not_name_is_not_claimed_by_a_concurrent_open(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"), ("w9", PRIMARY, "site"))
    run(repository, CREATE)
    after(repository, CREATE, {"stdout": created("w5")})
    assert decision(run(repository, "herdr workspace close w9 --group")) == "ask"


@pytest.mark.parametrize(("path", "label"), [("/repos/other", "site"), (PRIMARY, "renamed")])
def test_a_reused_id_with_another_path_or_label_asks(
    repository: Path, herdr: Path, tmp_path: Path, path: str, label: str
) -> None:
    open_primary(repository, tmp_path)
    workspace_list(tmp_path, ("w5", path, label))
    assert decision(run(repository, GROUP_CLOSE)) == "ask"


def test_a_closed_primary_expires_from_the_record(repository: Path, herdr: Path, tmp_path: Path) -> None:
    open_primary(repository, tmp_path)
    run(repository, GROUP_CLOSE)
    assert decision(run(repository, GROUP_CLOSE)) == "ask"


def test_the_path_falls_back_to_the_root_panes_foreground_directory(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, CREATE)
    result = {"workspace": {"workspace_id": "w5", "label": "site"}, "root_pane": {"foreground_cwd": PRIMARY}}
    after(repository, CREATE, {"stdout": json.dumps({"result": result})})
    assert decision(run(repository, GROUP_CLOSE)) == "allow"


def test_a_result_without_a_root_pane_directory_is_not_owned(repository: Path, herdr: Path, tmp_path: Path) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, CREATE)
    result = {"workspace": {"workspace_id": "w5", "label": "site"}, "root_pane": {"pane_id": "p1"}}
    after(repository, CREATE, {"stdout": json.dumps({"result": result})})
    assert decision(run(repository, GROUP_CLOSE)) == "ask"


def test_a_created_label_that_differs_from_the_asked_one_is_not_owned(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, CREATE)
    after(repository, CREATE, {"stdout": created(label="other")})
    assert decision(run(repository, GROUP_CLOSE)) == "ask"


def test_worktree_commands_no_longer_hand_over_a_parent_workspace(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    command = f"herdr worktree create --cwd {PRIMARY} --branch feat/x --no-focus"
    run(repository, command)
    after(repository, command, {"stdout": created()})
    assert decision(run(repository, "herdr workspace close w5")) == "ask"
    assert decision(run(repository, GROUP_CLOSE)) == "ask"
