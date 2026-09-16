#!/usr/bin/env -S python3 -IB
"""Explain dangerous Git operations before the provider's hard permission boundary."""

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import audit_log
import git_safety
import shell_syntax


def check(payload: dict) -> int:
    """Inspect parsed literal commands and reject uninspectable input."""
    command = ""
    try:
        if not isinstance(payload, dict):
            raise ValueError("invalid hook input: expected an object")
        command = payload.get("tool_input", {}).get("command") or ""
        for item in shell_syntax.parse(command):
            if reason := git_safety.reason(item.arguments):
                if item.wrapper_depth:
                    reason = f"shell wrapper contains {reason}"
                raise ValueError(f"{reason}.\n\nSegment: {shell_syntax.command_preview(item.raw)}")
    except (ValueError, TypeError, AttributeError) as error:
        message = f"BLOCKED: {error}\n\nUse a non-destructive command or ask the user to review this operation."
        audit_log.blocked(
            "Bash",
            command,
            message.splitlines()[0],
            "guard_dangerous_git.sh",
            payload.get("session_id", "") if isinstance(payload, dict) else "",
        )
        print(message, file=sys.stderr)
        return 2
    return 0


def main() -> int:
    if sys.argv[1:]:
        print("Usage: guard_git.py < hook-input.json", file=sys.stderr)
        return 0 if sys.argv[1:] in (["-h"], ["--help"]) else 1
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError) as error:
        audit_log.blocked("Bash", "", f"BLOCKED: {error}", "guard_dangerous_git.sh", "")
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2
    return check(payload)


if __name__ == "__main__":
    sys.exit(main())
