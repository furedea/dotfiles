#!/usr/bin/env -S python3 -IB
"""Mechanical lifecycle entry points for registered verification sessions."""

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "lib"))

import hook_input
import patch_input
import session_gate
import shell_syntax
from session_snapshot import repository_root
from session_store import SessionRecord, StateError, load, prune, register, session_directory


EVENTS = ("session-start", "pre-tool-use", "stop", "session-end")


def registered_record(provider: str, payload: dict, *, starting: bool = False) -> SessionRecord:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        raise StateError("Missing absolute session working directory")
    root = repository_root(Path(cwd))
    session = payload.get("session_id")
    if not isinstance(session, str):
        raise StateError("Missing provider session ID")
    directory = session_directory(root, provider, session)
    if starting:
        # New IDs after clear/fork have no reliable predecessor in native hook input.
        return register(root, provider, session, resuming=payload.get("source") != "startup")
    if not directory.exists():
        raise StateError("Missing verification registration; restart or resume to run SessionStart in this worktree")
    record = load(directory)
    with record.lock(blocking=False):
        if record.results().get("session_id") != session or record.provider != provider:
            raise StateError("Provider session differs from the registered session")
        record.touch()
    return record


def check_scope(record: SessionRecord, payload: dict) -> None:
    """Check observable tool paths; native permissions still govern shell execution."""
    value = payload.get("tool_input", {})
    if not isinstance(value, dict):
        raise StateError("Invalid tool input")
    cwd = Path(payload["cwd"])
    for key in ("cwd", "workdir"):
        if directory := value.get(key):
            require_inside(record, cwd / directory)
    command = value.get("command", value.get("cmd", ""))
    if isinstance(command, str):
        check_shell_directories(record, cwd, command)
    try:
        patch = hook_input.patch_body(value, payload.get("tool_name"))
    except ValueError as error:
        raise StateError(str(error)) from error
    for filename in patch_input.paths(patch):
        require_inside(record, cwd / filename)
    if payload.get("tool_name") in {"Write", "Edit", "MultiEdit", "apply_patch"}:
        if filename := value.get("file_path"):
            require_inside(record, cwd / filename)


def require_inside(record: SessionRecord, path: Path) -> None:
    if not path.expanduser().resolve().is_relative_to(record.root):
        raise StateError(
            f"Tool target is outside the registered worktree {record.root}; launch a session in that worktree"
        )


def check_shell_directories(record: SessionRecord, cwd: Path, command: str) -> None:
    try:
        commands = shell_syntax.parse(command)
    except shell_syntax.UnsupportedSyntax:
        return
    for parsed in commands:
        executable = Path(parsed.arguments[0]).name
        if executable in {"cd", "pushd"}:
            targets = [value for value in parsed.arguments[1:] if value not in {"--", "-L", "-P", "-e"}]
            if targets and targets[0] != "-":
                require_inside(record, cwd / Path(targets[0]).expanduser())
        elif executable == "git":
            for index, token in enumerate(parsed.arguments[:-1]):
                if token == "-C":
                    require_inside(record, cwd / Path(parsed.arguments[index + 1]).expanduser())


def dispatch(provider: str, event: str, payload: dict) -> dict[str, object]:
    record = registered_record(provider, payload, starting=event == "session-start")
    if event == "pre-tool-use":
        check_scope(record, payload)
    elif event == "stop":
        return {**session_gate.gate(record)}
    elif event == "session-end":
        with record.lock():
            record.end()
        prune()
    elif event == "session-start":
        prune()
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": f"Verification record: {record.directory}",
            }
        }
    return {}


def failure(event: str, payload: dict, error: Exception) -> dict[str, object]:
    message = f"Verification unresolved · {error}"
    if event == "pre-tool-use":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        }
    if event in {"stop", "verify"} and not payload.get("stop_hook_active"):
        return {"decision": "block", "reason": message}
    return {"systemMessage": message}


def main() -> int:
    arguments = sys.argv[1:]
    query = len(arguments) == 2 and arguments[0] == "status"
    explicit = query or (
        2 <= len(arguments) <= 3 and arguments[0] == "verify" and arguments[1:-1] in ([], ["--force"])
    )
    native = len(arguments) == 2 and arguments[0] in {"codex", "claude"} and arguments[1] in EVENTS
    if not (explicit or native):
        print(
            "Usage: verification_session.py codex|claude session-start|pre-tool-use|stop|session-end\n"
            "       verification_session.py verify [--force] /path/to/session-record\n"
            "       verification_session.py status /path/to/session-record\n"
            "Native events read the provider hook input from stdin.",
            file=sys.stderr,
        )
        return 0 if arguments in (["-h"], ["--help"]) else 1
    event = arguments[0] if explicit else arguments[1]
    status = 0
    payload: dict = {}
    try:
        if explicit:
            record = load(Path(arguments[-1]))
            if query:
                result = session_gate.status(record)
            else:
                result = session_gate.gate(record, force="--force" in arguments)
                status = int(result.get("decision") == "block" or session_gate.unresolved(record))
        else:
            payload = json.load(sys.stdin)
            if not isinstance(payload, dict):
                payload = {}
                raise StateError("Hook input must be an object")
            result = dispatch(arguments[0], event, payload)
    except (OSError, ValueError, TypeError, KeyError) as error:
        result = failure(event, payload, error)
        status = int(explicit)
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return status


if __name__ == "__main__":
    sys.exit(main())
