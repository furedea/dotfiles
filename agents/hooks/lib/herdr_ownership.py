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
        action = parsed.arguments[1:3]
        if (
            parsed.program_is_dynamic
            or Path(parsed.arguments[0]).name != "herdr"
            or action
            not in {
                ("agent", "start"),
                ("agent", "prompt"),
                ("workspace", "close"),
                ("worktree", "remove"),
                ("agent", "rename"),
            }
        ):
            continue
        try:
            simple = (
                len(commands) == 1 and parsed.arguments[0] == "herdr" and shell_syntax.is_one_simple_command(command)
            )
        except shell_syntax.UnsupportedSyntax:
            simple = False
        if not simple:
            raise ScopeError("Herdr ownership actions need one simple direct Herdr call")
        if action == ("agent", "start"):
            claim(record, target(parsed))
        elif action == ("agent", "prompt"):
            require_owned(record, target(parsed))
        elif action == ("workspace", "close"):
            require_closable(record, parsed)
        elif action == ("worktree", "remove"):
            require_removable(record, option_value(parsed, "--workspace"))
        else:
            raise ScopeError("Renaming a Herdr agent could hand one of this session's names to another pane")


def confirm(record: SessionRecord, command: str, response: object) -> None:
    """After a plain `workspace create` succeeded, own the primary workspace its result names.

    Only one simple call counts, so the output is Herdr's own and not something a list, pipe,
    redirection, or wrapper could have printed.
    """
    try:
        if not shell_syntax.is_one_simple_command(command):
            return
        commands = shell_syntax.parse(command)
    except shell_syntax.UnsupportedSyntax:
        return
    if len(commands) == 1 and is_plain_create(commands[0]):
        record_primary(record, commands[0], response)


def is_plain_create(parsed: shell_syntax.Command) -> bool:
    """`herdr workspace create --cwd <path> --label <label> --no-focus`, options in any order, all literal."""
    arguments = parsed.arguments
    if (
        parsed.program_is_dynamic
        or any(parsed.dynamic)
        or arguments[0] != "herdr"
        or arguments[1:3] != ("workspace", "create")
    ):
        return False
    rest = arguments[3:]
    options = [word for word in rest if word.startswith("--")]
    return (
        len(rest) == 5
        and sorted(options) == ["--cwd", "--label", "--no-focus"]
        and bool(option_value(parsed, "--cwd") and option_value(parsed, "--label"))
    )


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
    terminal = pane.get("terminal_id")
    if not (isinstance(terminal, str) and terminal):
        return
    entry = {"path": normpath(path), "label": label, "terminal": terminal}
    save(record, primaries={**primaries(record.directory), identifier: entry})


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
    """Plain closes only: Herdr itself refuses a primary's close while a linked workspace is open."""
    words = list(zip(parsed.arguments[3:], parsed.dynamic[3:], strict=True))
    options = {word for word, _ in words if word.startswith("-")}
    ids = [word if not dynamic else "" for word, dynamic in words if not word.startswith("-")]
    if options:
        raise ScopeError(f"Herdr workspace close option {min(options)} needs the user's judgment")
    require_owned_workspace(record, ids[0] if len(ids) == 1 else "")


def require_owned_workspace(record: SessionRecord, workspace: str) -> None:
    """A workspace may close when it is an idle primary this session created, or every agent in it is its own."""
    if workspace and workspace in primaries(record.directory):
        require_idle_primary(record, workspace)
        return
    names = [agent.get("name") for agent in live_agents() if workspace and agent.get("workspace_id") == workspace]
    if names and all(isinstance(name, str) and name in owned(record) for name in names):
        return
    shown = workspace or "chosen at run time"
    raise ScopeError(f"Herdr workspace {shown} does not hold only agents this session started")


def require_removable(record: SessionRecord, workspace: str) -> None:
    if workspace and workspace in primaries(record.directory):
        raise ScopeError(f"Herdr workspace {workspace} is a primary checkout; removing it deletes the repository")
    require_owned_workspace(record, workspace)


def require_idle_primary(record: SessionRecord, workspace: str) -> None:
    """Close the primary only while Herdr still serves what was recorded and nothing runs in it."""
    entry = primaries(record.directory)[workspace]
    if not matches_live(workspace, entry) or not holds_terminal(workspace, entry["terminal"]):
        raise ScopeError(f"Herdr workspace {workspace} no longer matches the primary this session created")
    if any(agent.get("workspace_id") == workspace for agent in live_agents()):
        raise ScopeError(f"Herdr workspace {workspace} still runs an agent")
    forget_primary(record.directory, workspace)


def holds_terminal(workspace: str, terminal: str) -> bool:
    """Whether the live workspace still has the recorded root terminal, which a reused ID or restart never repeats."""
    panes = herdr_result("pane", "list", "--workspace", workspace).get("panes", [])
    return any(isinstance(pane, dict) and pane.get("terminal_id") == terminal for pane in panes)


def matches_live(workspace: str, entry: dict[str, str]) -> bool:
    for item in workspace_items():
        if item["workspace_id"] == workspace:
            return item.get("label") == entry["label"] and live_path(item) == entry["path"]
    return False


def live_path(item: dict) -> str:
    """The workspace's checkout path, or its root pane's directory before a worktree attaches the group."""
    info = item.get("worktree")
    pane = item.get("root_pane")
    candidates = [
        info.get("checkout_path") if isinstance(info, dict) else None,
        pane.get("cwd") if isinstance(pane, dict) else None,
    ]
    return next((normpath(path) for path in candidates if isinstance(path, str) and path), "")


def primaries(directory: Path) -> dict[str, dict[str, str]]:
    path = directory / AGENTS_FILE
    value = read_json(path).get("primaries") if path.exists() else None
    if not isinstance(value, dict):
        return {}
    return {
        key: entry
        for key, entry in value.items()
        if isinstance(entry, dict) and all(isinstance(entry.get(name), str) for name in ("path", "label", "terminal"))
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
    """Open workspaces."""
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
