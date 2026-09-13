"""Evaluate generated prefixes and precise global/project command policy."""

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import audit_events
import command_policy
import shell_syntax


def policies(kind: str) -> tuple[list[dict], list[dict]]:
    """Load required global rules and optional project additions exactly once."""
    permissions = Path(os.environ.get("AGENT_COMMAND_PERMISSIONS", str(ROOT / "rules/command_permissions.json")))
    name = "allowed_commands.json" if kind == "allowed" else "forbidden_commands.json"
    environment = "AGENT_ALLOWED_COMMAND_RULES" if kind == "allowed" else "AGENT_FORBIDDEN_COMMAND_RULES"
    path = Path(os.environ.get(environment, str(ROOT / "rules" / name)))
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


def main(arguments: list[str]) -> int:
    """Deny known forbidden or uninspectable input; leave other decisions to the provider."""
    if len(arguments) != 1 or arguments[0] not in {"allowed", "forbidden"}:
        print("Usage: guard_commands.py <allowed|forbidden>", file=sys.stderr)
        return 1
    kind = arguments[0]
    payload: dict = {}
    command = ""
    try:
        prefixes, rules = policies(kind)
        try:
            candidate = json.load(sys.stdin)
        except json.JSONDecodeError as error:
            raise ValueError("failed to parse tool input JSON") from error
        if not isinstance(candidate, dict):
            raise ValueError("failed to parse tool input JSON: expected an object")
        payload = candidate
        command = payload.get("tool_input", {}).get("command") or ""
        for item in shell_syntax.parse(command):
            if kind == "allowed":
                governed = command_policy.prefix_reason(item.arguments, prefixes, "allow")
                reason = (
                    "command not in allowlist" if governed and not command_policy.regex_reason(item.raw, rules) else ""
                )
            else:
                reason = command_policy.prefix_reason(item.arguments, prefixes, "deny") or command_policy.regex_reason(
                    item.raw, rules
                )
            if reason:
                raise ValueError(f"{reason}.\n\nCommand: {item.raw}")
    except (ValueError, TypeError, AttributeError, OSError) as error:
        prefix = "forbidden command: " if kind == "forbidden" else ""
        message = f"BLOCKED: {prefix}{error}\n\nUse a non-destructive approved form, or ask the user to review the command policy."
        audit_events.blocked("Bash", command, str(error), f"guard_{kind}_commands.sh", payload.get("session_id", ""))
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
