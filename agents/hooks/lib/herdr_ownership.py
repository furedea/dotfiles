"""Let a session prompt only the Herdr agents it started.

Herdr runs outside the sandbox, so text sent to a pane runs there too. An agent this session
started carries the same sandbox and hooks, so prompting it is safe; any other target may be the
user's own shell or session, and prompting it needs the user's judgment.
"""

import json
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
            require_owned_workspace(record, target(parsed))
        elif action == ("worktree", "remove"):
            require_owned_workspace(record, option_value(parsed, "--workspace"))
        elif action == ("agent", "rename"):
            raise ScopeError("Renaming a Herdr agent could hand one of this session's names to another pane")


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


def require_owned_workspace(record: SessionRecord, workspace: str) -> None:
    """A workspace may be closed only when every agent in it is one this session started."""
    names = [agent.get("name") for agent in live_agents() if workspace and agent.get("workspace_id") == workspace]
    if names and all(isinstance(name, str) and name in owned(record) for name in names):
        return
    shown = workspace or "chosen at run time"
    raise ScopeError(f"Herdr workspace {shown} does not hold only agents this session started")


def claim(record: SessionRecord, name: str) -> None:
    if not name:
        raise ScopeError("Herdr agent name is a shell expansion, so this session cannot claim it")
    if name in live_agent_names():
        raise ScopeError(f"Herdr agent {name} already exists and was not started by this session")
    path = record.directory / AGENTS_FILE
    atomic_json(path, {"agents": sorted(owned(record) | {name})})


def require_owned(record: SessionRecord, name: str) -> None:
    if name and name in owned(record):
        return
    shown = name or "chosen at run time"
    raise ScopeError(f"Herdr agent {shown} was not started by this session; its pane may run outside the sandbox")


def owned(record: SessionRecord) -> set[str]:
    path = record.directory / AGENTS_FILE
    if not path.exists():
        return set()
    agents = read_json(path).get("agents", [])
    return {name for name in agents if isinstance(name, str)}


def live_agent_names() -> set[str]:
    """Names Herdr already serves; an unreachable Herdr cannot vouch for a name, so the claim asks."""
    return {agent["name"] for agent in live_agents() if isinstance(agent.get("name"), str) and agent["name"]}


def live_agents() -> list[dict]:
    try:
        result = subprocess.run(
            ["herdr", "agent", "list"], capture_output=True, text=True, check=True, timeout=LIST_TIMEOUT_SECONDS
        )
        agents = json.loads(result.stdout)["result"]["agents"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
        raise ScopeError("Herdr agents could not be listed, so ownership cannot be checked") from error
    return [agent for agent in agents if isinstance(agent, dict)]
