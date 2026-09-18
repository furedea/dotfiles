#!/usr/bin/env -S python3 -IB
"""Translate pi hook payloads at the boundary to shared hook implementations."""

import json
import os
from pathlib import Path
import sys

SCRIPT = Path(__file__).resolve()
COMMON = SCRIPT.parents[2] / (".claude/hooks" if SCRIPT.parent.parent.name.startswith(".") else "hooks")
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(COMMON / "lib"))

import audit_log
import guard_command
import guard_git
import guard_file
import hook_dispatch
import lint_format
import patch_input
import secret_path_policy
import shell_syntax
import verification_session

CANONICAL_TOOLS = {
    "bash": "Bash",
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "multi_edit": "MultiEdit",
    "notebook_edit": "NotebookEdit",
    "apply_patch": "apply_patch",
    "webfetch": "WebFetch",
    "web_search": "WebSearch",
}

NATIVE_EVENTS = {
    "session-start": "session_start",
    "pre-tool-use": "tool_call",
    "session-end": "session_shutdown",
}


def shared_directory() -> Path:
    return Path(os.environ.get("AGENT_HARNESS_ROOT", str(Path.home()))) / ".claude/hooks"


def manifest_path() -> Path:
    return Path(os.environ.get("AGENT_HARNESS_PI_MANIFEST", str(Path.home() / ".pi/agent/hooks.json")))


def normalized(payload: dict) -> dict:
    """Preserve the provider event while supplying the fields shared checks require."""
    result = dict(payload)
    values = result.get("tool_input")
    result["tool_input"] = dict(values) if isinstance(values, dict) else {}
    result["tool_input"].setdefault("file_path", result["tool_input"].get("path") or "")
    result.setdefault("cwd", os.getcwd())
    result.setdefault("prompt", result.get("text") or "")
    result["provider"] = "pi"
    if canonical := CANONICAL_TOOLS.get(result.get("tool_name") or ""):
        result["tool_name"] = canonical
    return result


def pi_result(event: str, result: dict) -> dict:
    """Convert the shared Claude-shaped decision into pi's blocking contract."""
    specific = result.get("hookSpecificOutput")
    if isinstance(specific, dict) and specific.get("permissionDecision") == "deny":
        reason = specific.get("permissionDecisionReason") or "Blocked by hook policy"
        return {"decision": "block", "reason": reason}
    if message := result.get("systemMessage"):
        return {"systemMessage": message}
    return result


def native(event: str, payload: dict) -> int:
    normalized_payload = normalized(payload)
    try:
        result = verification_session.dispatch("pi", event, normalized_payload)
    except (OSError, ValueError, TypeError, KeyError) as error:
        result = verification_session.failure(event, normalized_payload, error)
    print(json.dumps(pi_result(event, result), ensure_ascii=True, separators=(",", ":")))
    return 0


def audit(kind: str, payload: dict) -> int:
    context = normalized(payload)
    entry = audit_log.record(kind, context, "pi")
    cwd = context.get("cwd") or "."
    audit_log.append_record(entry, cwd=Path(cwd))
    return 0


def patch_text(values: dict) -> str:
    return values.get("patch") or values.get("input") or values.get("command") or ""


def lint(payload: dict) -> int:
    """Report shared quality diagnostics using the post-tool JSON contract."""
    lint_format.emit(lint_format.diagnostics(normalized(payload)))
    return 0


def harness(payload: dict) -> int:
    values = normalized(payload).get("tool_input") or {}
    candidates = [values.get("file_path") or values.get("path") or ""]
    candidates += patch_input.paths(patch_text(values))
    for name in candidates:
        if not name:
            continue
        absolute = name if name.startswith(("/", "~/")) else str(Path.cwd() / name)
        if status := guard_file.check(
            "harness",
            normalized(payload) | {"tool_name": "apply_patch", "tool_input": {"file_path": absolute}},
            shared_directory(),
        ):
            return status
    return 0


def check_paths(mode: str, payload: dict) -> int:
    policy = Path(
        os.environ.get("AGENT_SECRET_PATH_POLICY", str(shared_directory() / "rules/secret_path_policy.json"))
    )
    rules = secret_path_policy.load(policy)
    values = normalized(payload).get("tool_input") or {}
    command = values.get("command") or values.get("cmd") or ""
    if mode == "command":
        try:
            commands = shell_syntax.parse(command)
        except shell_syntax.UnsupportedSyntax as error:
            raise ValueError(f"{error}\n\nCommand: {shell_syntax.command_preview(command)}") from error
        candidates = [word for item in commands for word in (*item.arguments, *item.redirections)]
        candidates += [word.partition("=")[2] for word in candidates if "=" in word]
    else:
        candidates = [values.get("file_path") or values.get("path") or "", *patch_input.paths(patch_text(values))]
    context = normalized(payload)
    for value in candidates:
        if rule := secret_path_policy.blocked_rule(value, rules):
            audit_log.blocked(
                "Bash" if mode == "command" else "apply_patch",
                command if mode == "command" else value,
                f"{rule['reason']}: {value}",
                "adapt_guard_secret_paths.sh",
                payload.get("session_id") or "",
                payload=context,
                targets=() if mode == "command" else (value,),
            )
            raise ValueError(
                f"secret path policy matched.\n\nPath: {value}\nPattern: {rule['pattern']}\n\nWhy:\n  {rule['reason']}"
            )
    return 0


def content(mode: str, payload: dict) -> int:
    if mode == "apply-patch":
        values = normalized(payload).get("tool_input") or {}
        return guard_file.check(
            "write",
            normalized(payload)
            | {"tool_name": "Edit", "tool_input": {"content": patch_input.added_text(patch_text(values))}},
            shared_directory(),
        )
    return guard_file.check(mode, normalized(payload), shared_directory())


def dispatch(kind: str, arguments: list[str], payload: dict) -> int:
    values = normalized(payload).get("tool_input") or {}
    if kind == "native":
        return native(arguments[0], payload)
    if kind == "audit":
        return audit(arguments[0], payload)
    if kind == "dispatch":
        return hook_dispatch.run(manifest_path(), arguments[0], payload)
    if kind == "shell":
        command = normalized(payload) | {
            "tool_name": "Bash",
            "tool_input": {"command": values.get("command") or values.get("cmd") or ""},
        }
        if arguments[0] in {"allowed", "forbidden"}:
            return guard_command.check(arguments[0], command, shared_directory())
        if arguments[0] == "git":
            return guard_git.check(command)
        return guard_file.check("commit", command, shared_directory())
    if kind == "lint":
        return lint(payload)
    if kind == "harness":
        return harness(payload)
    if kind == "paths":
        return check_paths(arguments[0], payload)
    return content(arguments[0], payload)


def main(arguments: list[str]) -> int:
    kind = arguments[0] if arguments else ""
    rest = arguments[1:]
    valid = (
        (kind == "native" and len(rest) == 1 and rest[0] in NATIVE_EVENTS)
        or (kind == "audit" and len(rest) == 1 and rest[0] in {"tool", "compaction"})
        or (kind == "dispatch" and len(rest) == 1)
        or (kind in {"lint", "harness"} and not rest)
        or (kind == "shell" and len(rest) == 1 and rest[0] in {"allowed", "forbidden", "git", "commit"})
        or (kind == "paths" and len(rest) == 1 and rest[0] in {"command", "patch"})
        or (kind == "content" and len(rest) == 1 and rest[0] in {"prompt", "read", "write", "apply-patch"})
    )
    if not valid or any(value in {"-h", "--help"} for value in rest):
        print(
            "Usage: hook_adapter.py <native session-start/pre-tool-use/session-end"
            "|audit tool/compaction|dispatch <event>|shell allowed/forbidden/git/commit|lint|harness"
            "|paths command/patch|content prompt/read/write/apply-patch>",
            file=sys.stderr,
        )
        return 1
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            payload = {}
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd:
            os.chdir(cwd)
        return dispatch(kind, rest, payload)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
