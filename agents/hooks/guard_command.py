#!/usr/bin/env -S python3 -IB
"""Evaluate generated prefixes and precise global/project command policy."""

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import audit_log
import command_policy
import shell_syntax


def policies(kind: str, directory: Path) -> tuple[list[dict], list[dict]]:
    """Load required global rules and optional project additions exactly once."""
    permissions = Path(os.environ.get("AGENT_COMMAND_PERMISSIONS", str(directory / "rules/command_permissions.json")))
    name = "allowed_commands.json" if kind == "allowed" else "forbidden_commands.json"
    environment = "AGENT_ALLOWED_COMMAND_RULES" if kind == "allowed" else "AGENT_FORBIDDEN_COMMAND_RULES"
    path = Path(os.environ.get(environment, str(directory / "rules" / name)))
    try:
        prefixes = command_policy.load_rules(permissions, prefixes=True)
    except ValueError as error:
        raise ValueError(f"invalid command permissions: {permissions}") from error
    try:
        rules = command_policy.load_rules(path)
    except ValueError as error:
        if kind == "forbidden":
            raise ValueError(f"forbidden command regex rules were not found or are invalid: {path}") from error
        raise ValueError(f"invalid global {kind} command rules: {path}") from error
    if project := command_policy.project_file(name):
        try:
            rules += command_policy.load_rules(project)
        except ValueError as error:
            raise ValueError(f"invalid project {kind} command rules: {project}") from error
    return prefixes, rules


def objection(
    kind: str, item: shell_syntax.Command, candidate: shell_syntax.Command, prefixes: list[dict], rules: list[dict]
) -> str:
    """Judge one segment by its literal text and by its canonical program and subcommand."""
    matched = command_policy.regex_reason(item.raw, rules) or command_policy.regex_reason(candidate.raw, rules)
    if kind == "allowed":
        governed = command_policy.prefix_reason(candidate.arguments, prefixes, "allow")
        return "command not in allowlist" if governed and not matched else ""
    return command_policy.prefix_reason(candidate.arguments, prefixes, "deny") or matched


def check(kind: str, payload: dict, directory: Path = ROOT) -> int:
    """Enforce command policy for an already decoded provider payload."""
    command = ""
    try:
        prefixes, rules = policies(kind, directory)
        if not isinstance(payload, dict):
            raise ValueError("failed to parse tool input JSON: expected an object")
        command = payload.get("tool_input", {}).get("command") or ""
        for item in shell_syntax.parse(command):
            if reason := objection(kind, item, command_policy.canonical(item), prefixes, rules):
                raise ValueError(f"{reason}.\n\nCommand: {shell_syntax.command_preview(item.raw)}")
    except (ValueError, TypeError, AttributeError, OSError) as error:
        prefix = "forbidden command: " if kind == "forbidden" else ""
        message = f"BLOCKED: {prefix}{error}\n\nUse a non-destructive approved form, or ask the user to review the command policy."
        audit_log.blocked(
            "Bash",
            command,
            str(error),
            f"guard_{kind}_commands.sh",
            payload.get("session_id", "") if isinstance(payload, dict) else "",
            payload=payload if isinstance(payload, dict) else None,
        )
        print(message, file=sys.stderr)
        return 2
    return 0


def main(arguments: list[str]) -> int:
    if len(arguments) != 1 or arguments[0] not in {"allowed", "forbidden"}:
        print("Usage: guard_command.py <allowed|forbidden>", file=sys.stderr)
        return 1
    try:
        payload = json.load(sys.stdin)
    except ValueError, OSError:
        audit_log.blocked("Bash", "", "failed to parse tool input JSON", f"guard_{arguments[0]}_commands.sh", "")
        print("BLOCKED: failed to parse tool input JSON", file=sys.stderr)
        return 2
    return check(arguments[0], payload)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
