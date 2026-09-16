#!/usr/bin/env -S python3 -IB
"""Mechanical lifecycle entry points for registered verification sessions."""

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "lib"))

import patch_input
import session_gate
import shell_syntax
from session_snapshot import repository_root
from session_store import Run, StateError, load, prune, register, session_directory


EVENTS = ("session-start", "pre-tool-use", "stop", "session-end")


def registered_run(provider: str, payload: dict, *, starting: bool = False) -> Run:
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
    run = load(directory)
    with run.lock(blocking=False):
        if run.results().get("session_id") != session or run.provider != provider:
            raise StateError("Provider session differs from the registered session")
        run.touch()
    return run


def check_scope(run: Run, payload: dict) -> None:
    """Check observable tool paths; native permissions still govern shell execution."""
    value = payload.get("tool_input", {})
    if not isinstance(value, dict):
        raise StateError("Invalid tool input")
    cwd = Path(payload["cwd"])
    for key in ("cwd", "workdir"):
        if directory := value.get(key):
            require_inside(run, cwd / directory)
    command = value.get("command", value.get("cmd", ""))
    if isinstance(command, str):
        check_shell_directories(run, cwd, command)
    patch = value.get("patch", value.get("input", command))
    if isinstance(patch, str):
        for filename in patch_input.paths(patch):
            require_inside(run, cwd / filename)
    if payload.get("tool_name") in {"Write", "Edit", "MultiEdit", "apply_patch"}:
        if filename := value.get("file_path"):
            require_inside(run, cwd / filename)


def require_inside(run: Run, path: Path) -> None:
    if not path.expanduser().resolve().is_relative_to(run.root):
        raise StateError(
            f"Tool target is outside the registered worktree {run.root}; launch a session in that worktree"
        )


def check_shell_directories(run: Run, cwd: Path, command: str) -> None:
    try:
        commands = shell_syntax.parse(command)
    except shell_syntax.UnsupportedSyntax:
        return
    for parsed in commands:
        executable = Path(parsed.arguments[0]).name
        if executable in {"cd", "pushd"}:
            targets = [value for value in parsed.arguments[1:] if value not in {"--", "-L", "-P", "-e"}]
            if targets and targets[0] != "-":
                require_inside(run, cwd / Path(targets[0]).expanduser())
        elif executable == "git":
            for index, token in enumerate(parsed.arguments[:-1]):
                if token == "-C":
                    require_inside(run, cwd / Path(parsed.arguments[index + 1]).expanduser())


def dispatch(provider: str, event: str, payload: dict) -> dict[str, object]:
    run = registered_run(provider, payload, starting=event == "session-start")
    if event == "pre-tool-use":
        check_scope(run, payload)
    elif event == "stop":
        return {**session_gate.stop(run)}
    elif event == "session-end":
        with run.lock():
            run.end()
        prune()
    elif event == "session-start":
        prune()
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
    explicit = 2 <= len(arguments) <= 3 and arguments[0] == "verify" and arguments[1:-1] in ([], ["--force"])
    native = len(arguments) == 2 and arguments[0] in {"codex", "claude"} and arguments[1] in EVENTS
    if not (explicit or native):
        print(
            "Usage: verification_session.py codex|claude session-start|pre-tool-use|stop|session-end\n"
            "       verification_session.py verify [--force] /path/to/session-record\n"
            "Native events read the provider hook input from stdin.",
            file=sys.stderr,
        )
        return 0 if arguments in (["-h"], ["--help"]) else 1
    event = arguments[0] if explicit else arguments[1]
    status = 0
    payload: dict = {}
    try:
        if explicit:
            run = load(Path(arguments[-1]))
            result = session_gate.stop(run, force="--force" in arguments)
            status = int(result.get("decision") == "block" or session_gate.unresolved(run))
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
