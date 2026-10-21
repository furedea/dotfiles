"""Shared Herdr ownership command and response helpers."""

import json
from pathlib import Path
import subprocess
import sys

from tests.runtime import REPO_ROOT


hook = REPO_ROOT / "agents/hooks/verification_session.py"


TERMINAL = "term_65e57fd60160846c"


PRIMARY = "/repos/site"
CREATE = f"herdr workspace create --cwd {PRIMARY} --label site --no-focus"
CLOSE = "herdr workspace close w5"


def run(repository: Path, command: str, session: str = "session") -> dict:
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(hook), "codex", "pre-tool-use"],
        input=json.dumps(
            {"cwd": str(repository), "session_id": session, "tool_name": "Bash", "tool_input": {"command": command}}
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return json.loads(result.stdout)


def decision(output: dict) -> str:
    return output.get("hookSpecificOutput", {}).get("permissionDecision", "allow")


def workspace_list(tmp_path: Path, *entries: tuple[str, str, str], linked: tuple[str, ...] = ()) -> None:
    """Open workspaces as (id, checkout path, label)."""
    rows = [
        {"workspace_id": ws, "label": label, "worktree": {"checkout_path": path, "is_linked_worktree": ws in linked}}
        for ws, path, label in entries
    ]
    (tmp_path / "workspaces.json").write_text(json.dumps({"result": {"workspaces": rows}}))


def created(workspace: str = "w5", label: str = "site", cwd: str = PRIMARY) -> str:
    """The shape `herdr workspace create` returns: no checkout path, the directory is the root pane's."""
    result = {
        "type": "workspace_created",
        "workspace": {"workspace_id": workspace, "label": label},
        "root_pane": {"pane_id": "p1", "cwd": cwd, "terminal_id": TERMINAL},
    }
    return json.dumps({"result": result})


def after(repository: Path, command: str, response: object, session: str = "session") -> None:
    subprocess.run(
        [sys.executable, "-I", "-B", str(hook), "codex", "post-tool-use"],
        input=json.dumps(
            {
                "cwd": str(repository),
                "session_id": session,
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


def open_primary(repository: Path, tmp_path: Path) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, CREATE)
    after(repository, CREATE, {"stdout": created()})


def set_terminals(tmp_path: Path, *terminals: str) -> None:
    panes = [{"pane_id": f"p{index}", "terminal_id": terminal} for index, terminal in enumerate(terminals, 1)]
    (tmp_path / "panes.json").write_text(json.dumps({"result": {"panes": panes}}))


def set_agents(names: Path, text: str) -> None:
    """Prepare the agent listing when live agents change, without a Python child."""
    agents = []
    for line in text.splitlines():
        name, workspace, terminal, session = (line.split() + ["", "", ""])[:4]
        agents.append(
            {
                "name": name,
                "workspace_id": workspace,
                "pane_id": "p1",
                "terminal_id": terminal or "term_agent",
                "agent_session": {"value": session or "session_agent"},
            }
        )
    names.write_text(text)
    (names.parent / "agents.json").write_text(json.dumps({"result": {"agents": agents}}))


def start_agent(repository: Path, herdr: Path, workspace: str, *, command: str = "") -> None:
    command = command or f"herdr agent start lane-a --kind claude --pane {workspace}:p1"
    assert decision(run(repository, command)) == "allow"
    agent = {
        "name": "lane-a",
        "workspace_id": workspace,
        "pane_id": "p1",
        "terminal_id": "term_agent",
        "agent_session": {"value": "session_agent"},
    }
    after(repository, command, {"stdout": json.dumps({"result": {"type": "agent_started", "agent": agent}})})
    set_agents(herdr, f"lane-a {workspace} term_agent\n")


def open_lane(repository: Path, tmp_path: Path) -> None:
    command = "herdr worktree create --workspace w5 --branch feat/x --label lane --no-focus"
    workspace_list(tmp_path, ("w5", PRIMARY, "site"), ("w6", "/lanes/w6", "lane"), linked=("w6",))
    result = json.loads(created("w6", "lane", PRIMARY))
    result["result"]["type"] = "worktree_created"
    result["result"]["worktree"] = {"path": "/lanes/w6"}
    after(repository, command, {"stdout": json.dumps(result)})
