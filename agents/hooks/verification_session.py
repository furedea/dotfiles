#!/usr/bin/env -S python3 -IB
"""Mechanical lifecycle entry points for registered verification sessions."""

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "lib"))

import patch_input
import session_gate
import shell_syntax
from session_snapshot import repository_root
from session_store import Run, StateError, load, prune


def environment_run() -> Run:
    directory = os.environ.get("AGENT_VERIFICATION_RUN")
    if not directory:
        raise StateError(
            "Missing verification registration; restart through the codex/claude launcher in the target worktree"
        )
    return load(Path(directory))


def registered_run(payload: dict) -> Run:
    run = environment_run()
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or repository_root(Path(cwd)) != run.root:
        raise StateError(f"Session worktree differs from the registered worktree: {run.root}")
    session = payload.get("session_id")
    if not isinstance(session, str):
        raise StateError("Missing provider session ID")
    with run.lock():
        run.bind(session, resuming=payload.get("source") == "resume", clearing=payload.get("source") == "clear")
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


def dispatch(event: str, payload: dict) -> dict[str, object]:
    run = registered_run(payload)
    if event == "pre":
        check_scope(run, payload)
    elif event in {"stop", "check", "retry"}:
        return {**session_gate.stop(run, force=event == "retry")}
    elif event == "end":
        with run.lock():
            run.end()
        prune()
    return {}


def failure(event: str, payload: dict, error: Exception) -> dict[str, object]:
    message = f"Verification unresolved · {error}"
    if event == "pre":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        }
    if event == "start":
        return {"continue": False, "stopReason": message}
    if event in {"stop", "check", "retry"} and not payload.get("stop_hook_active"):
        return {"decision": "block", "reason": message}
    return {"systemMessage": message}


def main() -> int:
    arguments = sys.argv[1:]
    events = {"start", "pre", "stop", "end", "check", "retry"}
    if len(arguments) != 1 or arguments[0] not in events:
        print("Usage: verification_session.py start|pre|stop|end|check|retry < hook-input.json", file=sys.stderr)
        return 0 if arguments in (["-h"], ["--help"]) else 1
    event = arguments[0]
    explicit = event in {"check", "retry"}
    status = 0
    payload: dict = {}
    try:
        if explicit:
            run = environment_run()
            payload = {"cwd": str(run.root), "session_id": run.results().get("session_id")}
        else:
            payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            payload = {}
            raise StateError("Hook input must be an object")
        result = dispatch(event, payload)
        if explicit:
            status = int(result.get("decision") == "block" or session_gate.unresolved(environment_run()))
    except (OSError, ValueError, TypeError, KeyError) as error:
        result = failure(event, payload, error)
        status = int(explicit)
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return status


if __name__ == "__main__":
    sys.exit(main())
