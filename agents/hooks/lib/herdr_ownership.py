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
        elif action == ("worktree", "create"):
            note_opened_parent(record, option_value(parsed, "--cwd"))
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


def note_opened_parent(record: SessionRecord, repository: str) -> None:
    """Remember a repository workspace that `worktree create` is about to open for its group."""
    if not repository or repository in open_checkouts():
        return
    save(record, parents=sorted(stored(record, "parents") | {repository}))


def require_owned_workspace(record: SessionRecord, workspace: str) -> None:
    """A workspace may close when every agent in it is this session's, or it is an empty parent it opened."""
    names = [agent.get("name") for agent in live_agents() if workspace and agent.get("workspace_id") == workspace]
    if names and all(isinstance(name, str) and name in owned(record) for name in names):
        return
    checkout = next((path for path, opened in open_checkouts().items() if opened == workspace), "")
    if not names and checkout and checkout in stored(record, "parents"):
        return
    shown = workspace or "chosen at run time"
    raise ScopeError(f"Herdr workspace {shown} does not hold only agents this session started")


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


def save(record: SessionRecord, **values: list[str]) -> None:
    path = record.directory / AGENTS_FILE
    current = read_json(path) if path.exists() else {}
    atomic_json(path, {**current, **values})


def open_checkouts() -> dict[str, str]:
    """Map each open primary-checkout workspace's path to its id."""
    workspaces = herdr_result("workspace", "list").get("workspaces", [])
    return {
        item["worktree"]["checkout_path"]: item["workspace_id"]
        for item in workspaces
        if isinstance(item, dict)
        and isinstance(item.get("worktree"), dict)
        and not item["worktree"].get("is_linked_worktree")
        and isinstance(item["worktree"].get("checkout_path"), str)
    }


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
