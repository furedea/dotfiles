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
import hook_decision
from hook_decision import Verdict
import shell_syntax


RULE = "guard_dangerous_git.sh"


def decide(payload: dict) -> Verdict:
    """Inspect parsed literal commands; hand uninspectable input to the user and deny destructive forms."""
    command = ""
    try:
        if not isinstance(payload, dict):
            raise ValueError("invalid hook input: expected an object")
        command = payload.get("tool_input", {}).get("command") or ""
        try:
            commands = shell_syntax.parse(command)
        except shell_syntax.UnsupportedSyntax as error:
            preview = shell_syntax.command_preview(command)
            verdict = hook_decision.ask(f"Needs review: {error}.\n\nCommand: {preview}", "syntax")
            audit_log.escalated(
                "Bash", command, verdict.reason, RULE, session(payload), payload=payload, detail="syntax"
            )
            return verdict
        for item in commands:
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
            RULE,
            session(payload),
            payload=payload if isinstance(payload, dict) else None,
        )
        return hook_decision.deny(message)
    return hook_decision.ALLOW


def session(payload: object) -> str:
    return payload.get("session_id", "") if isinstance(payload, dict) else ""


def check(payload: dict) -> int:
    """Enforce the dangerous-Git policy for an already decoded provider payload."""
    return hook_decision.emit(decide(payload))


def main() -> int:
    if sys.argv[1:]:
        print("Usage: guard_git.py < hook-input.json", file=sys.stderr)
        return 0 if sys.argv[1:] in (["-h"], ["--help"]) else 1
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError) as error:
        audit_log.blocked("Bash", "", f"BLOCKED: {error}", RULE, "")
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2
    return check(payload)


if __name__ == "__main__":
    sys.exit(main())
