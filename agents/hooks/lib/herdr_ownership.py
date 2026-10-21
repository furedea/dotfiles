"""Let a session prompt only the Herdr agents it started.

Herdr runs outside the sandbox, so text sent to a pane runs there too. An agent this session
started carries the same sandbox and hooks, so prompting it is safe; any other target may be the
user's own shell or session, and prompting it needs the user's judgment.
"""

import json
import os
from pathlib import Path
import subprocess

from session_store import ScopeError, SessionRecord, atomic_json, read_json
import shell_syntax


AGENTS_FILE = "herdr_agents.json"
LIST_TIMEOUT_SECONDS = 5


def check(record: SessionRecord, command: str) -> None:
    """Record agents this command starts and refuse prompts to agents the session did not start."""
    try:
        commands = shell_syntax.parse(command)
    except shell_syntax.UnsupportedSyntax:
        return
    for parsed in commands:
        if parsed.program_is_dynamic or Path(parsed.arguments[0]).name != "herdr":
            continue
        action = parsed.arguments[1:3]
        if action == ("agent", "start"):
            claim(record, target(parsed))
        elif action == ("agent", "prompt"):
            require_owned(record, target(parsed))
        elif action == ("workspace", "close"):
            require_closable(record, parsed)
        elif action == ("worktree", "remove"):
            require_owned_workspace(record, option_value(parsed, "--workspace"))
        elif action == ("agent", "rename"):
            raise ScopeError("Renaming a Herdr agent could hand one of this session's names to another pane")


def confirm(record: SessionRecord, command: str, response: object) -> None:
    """After `workspace create` succeeded, own the primary workspace its result names."""
    try:
        commands = shell_syntax.parse(command)
    except shell_syntax.UnsupportedSyntax:
        return
    for parsed in commands:
        if parsed.program_is_dynamic or Path(parsed.arguments[0]).name != "herdr":
            continue
        if parsed.arguments[1:3] == ("workspace", "create"):
            record_primary(record, parsed, response)


def target(parsed: shell_syntax.Command) -> str:
    if len(parsed.arguments) < 4 or parsed.dynamic[3]:
        return ""
    return parsed.arguments[3]


def option_value(parsed: shell_syntax.Command, option: str) -> str:
    arguments = parsed.arguments
    for index, argument in enumerate(arguments[:-1]):
        if argument == option and not parsed.dynamic[index + 1]:
            return arguments[index + 1]
    return ""


def record_primary(record: SessionRecord, parsed: shell_syntax.Command, response: object) -> None:
    """Own the workspace a successful result names; its path is the root pane's, since the result has no checkout."""
    result = created_result(response)
    workspace = result.get("workspace")
    pane = result.get("root_pane")
    if not isinstance(workspace, dict) or not isinstance(pane, dict):
        return
    identifier, label = workspace.get("workspace_id"), workspace.get("label")
    path = next((pane[key] for key in ("cwd", "foreground_cwd") if isinstance(pane.get(key), str) and pane[key]), "")
    if not (isinstance(identifier, str) and isinstance(label, str) and label and path):
        return
    if label != option_value(parsed, "--label"):
        return
    save(record, primaries={**primaries(record.directory), identifier: {"path": normpath(path), "label": label}})


def created_result(response: object) -> dict:
    """The `result` object of a command's JSON output; anything failed or malformed gives none."""
    if isinstance(response, dict):
        if response.get("interrupted") or response.get("is_error") or response.get("isError"):
            return {}
        response = response.get("stdout")
    if not isinstance(response, str):
        return {}
    try:
        result = json.loads(response)["result"]
    except TypeError, ValueError, KeyError:
        return {}
    return result if isinstance(result, dict) else {}


def require_closable(record: SessionRecord, parsed: shell_syntax.Command) -> None:
    words = list(zip(parsed.arguments[3:], parsed.dynamic[3:], strict=True))
    options = {word for word, _ in words if word.startswith("-")}
    ids = [word if not dynamic else "" for word, dynamic in words if not word.startswith("-")]
    workspace = ids[0] if len(ids) == 1 else ""
    if options == {"--group"}:
        require_owned_group(record, workspace)
    elif options:
        raise ScopeError(f"Herdr workspace close option {min(options)} needs the user's judgment")
    else:
        require_owned_workspace(record, workspace)


def require_owned_workspace(record: SessionRecord, workspace: str) -> None:
    """A workspace may close when it holds agents and every one of them is this session's."""
    names = [agent.get("name") for agent in live_agents() if workspace and agent.get("workspace_id") == workspace]
    if names and all(isinstance(name, str) and name in owned(record) for name in names):
        return
    shown = workspace or "chosen at run time"
    raise ScopeError(f"Herdr workspace {shown} does not hold only agents this session started")


def require_owned_group(record: SessionRecord, workspace: str) -> None:
    """A group may close when this session created its primary and only this session's lanes run in it."""
    entry = live_primary(record, workspace)
    shown = workspace or "chosen at run time"
    if not entry:
        raise ScopeError(f"Herdr workspace {shown} is not a primary workspace this session created")
    group = group_workspaces(workspace, entry["path"])
    names = [agent.get("name") for agent in live_agents() if agent.get("workspace_id") in group]
    if not all(isinstance(name, str) and name in owned(record) for name in names):
        raise ScopeError(f"Herdr group {shown} holds an agent this session did not start")
    forget_primary(record.directory, workspace)


def live_primary(record: SessionRecord, workspace: str) -> dict[str, str]:
    """The recorded primary, only while the live workspace still has the recorded ID, path, and label."""
    entry = primaries(record.directory).get(workspace)
    return entry if entry and matches_live(workspace, entry) else {}


def matches_live(workspace: str, entry: dict[str, str]) -> bool:
    for item in workspace_items():
        info = item["worktree"]
        if (
            item["workspace_id"] == workspace
            and not info.get("is_linked_worktree")
            and isinstance(info.get("checkout_path"), str)
            and normpath(info["checkout_path"]) == entry["path"]
            and item.get("label") == entry["label"]
        ):
            return True
    return False


def idle_primaries(directory: Path, repository: Path) -> list[str]:
    """Recorded primaries of one repository that still match the live workspace and hold no worktree or agent."""
    idle = []
    for workspace, entry in primaries(directory).items():
        if Path(entry["path"]).resolve() != repository.resolve() or not matches_live(workspace, entry):
            continue
        if group_workspaces(workspace, entry["path"]) != {workspace}:
            continue
        if any(agent.get("workspace_id") == workspace for agent in live_agents()):
            continue
        idle.append(workspace)
    return idle


def group_workspaces(primary: str, path: str) -> set[str]:
    worktrees = herdr_result("worktree", "list", "--cwd", path).get("worktrees", [])
    opened = {item.get("open_workspace_id") for item in worktrees if isinstance(item, dict)}
    return {primary} | {value for value in opened if isinstance(value, str)}


def primaries(directory: Path) -> dict[str, dict[str, str]]:
    path = directory / AGENTS_FILE
    value = read_json(path).get("primaries") if path.exists() else None
    if not isinstance(value, dict):
        return {}
    return {
        key: entry
        for key, entry in value.items()
        if isinstance(entry, dict) and isinstance(entry.get("path"), str) and isinstance(entry.get("label"), str)
    }


def forget_primary(directory: Path, workspace: str) -> None:
    """The record ends with the close, so a reused ID never inherits it."""
    update(directory, primaries={key: entry for key, entry in primaries(directory).items() if key != workspace})


def normpath(path: str) -> str:
    return os.path.normpath(path)


def claim(record: SessionRecord, name: str) -> None:
    if not name:
        raise ScopeError("Herdr agent name is a shell expansion, so this session cannot claim it")
    if name in live_agent_names():
        raise ScopeError(f"Herdr agent {name} already exists and was not started by this session")
    save(record, agents=sorted(owned(record) | {name}))


def require_owned(record: SessionRecord, name: str) -> None:
    if name and name in owned(record):
        return
    shown = name or "chosen at run time"
    raise ScopeError(f"Herdr agent {shown} was not started by this session; its pane may run outside the sandbox")


def owned(record: SessionRecord) -> set[str]:
    return stored(record, "agents")


def stored(record: SessionRecord, key: str) -> set[str]:
    path = record.directory / AGENTS_FILE
    if not path.exists():
        return set()
    return {value for value in read_json(path).get(key, []) if isinstance(value, str)}


def save(record: SessionRecord, **values: object) -> None:
    update(record.directory, **values)


def update(directory: Path, **values: object) -> None:
    path = directory / AGENTS_FILE
    current = read_json(path) if path.exists() else {}
    atomic_json(path, {**current, **values})


def workspace_items() -> list[dict]:
    """Open workspaces that carry worktree details."""
    workspaces = herdr_result("workspace", "list").get("workspaces", [])
    return [
        item
        for item in workspaces
        if isinstance(item, dict)
        and isinstance(item.get("workspace_id"), str)
        and isinstance(item.get("worktree"), dict)
    ]


def live_agent_names() -> set[str]:
    """Names Herdr already serves; an unreachable Herdr cannot vouch for a name, so the claim asks."""
    return {agent["name"] for agent in live_agents() if isinstance(agent.get("name"), str) and agent["name"]}


def live_agents() -> list[dict]:
    agents = herdr_result("agent", "list").get("agents", [])
    return [agent for agent in agents if isinstance(agent, dict)]


def herdr_result(*command: str) -> dict:
    """Read a Herdr listing; an unreachable Herdr cannot vouch for anything, so the check asks."""
    try:
        result = subprocess.run(
            ["herdr", *command], capture_output=True, text=True, check=True, timeout=LIST_TIMEOUT_SECONDS
        )
        value = json.loads(result.stdout)["result"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
        raise ScopeError(f"Herdr {' '.join(command)} failed, so ownership cannot be checked") from error
    if not isinstance(value, dict):
        raise ScopeError(f"Herdr {' '.join(command)} returned no result, so ownership cannot be checked")
    return value
