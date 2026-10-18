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
        verdict = inspect(command)
        if verdict.decision == "ask":
            audit_log.escalated(audit_log.Refusal("Bash", RULE, session(payload), payload=payload, detail="syntax"))
        return verdict
    except (ValueError, TypeError, AttributeError) as error:
        message = f"BLOCKED: {error}\n\nUse a non-destructive command or ask the user to review this operation."
        audit_log.blocked(
            audit_log.Refusal("Bash", RULE, session(payload), payload=payload if isinstance(payload, dict) else None)
        )
        return hook_decision.deny(message)


def inspect(command: str) -> Verdict:
    """Ask about the first segment a run-time word could hide, and raise for the first destructive one."""
    try:
        commands = shell_syntax.parse(command)
    except shell_syntax.UnsupportedSyntax as error:
        preview = shell_syntax.command_preview(command)
        return hook_decision.ask(f"Needs review: {error}.\n\nCommand: {preview}", "syntax")
    for item in commands:
        if hides_verdict(item):
            preview = shell_syntax.command_preview(item.raw)
            return hook_decision.ask(
                f"Needs review: a shell expansion decides what this Git command does.\n\nSegment: {preview}",
                "syntax",
            )
        if reason := segment_reason(item):
            raise ValueError(reason)
    return hook_decision.ALLOW


def segment_reason(item: shell_syntax.Command) -> str:
    reason = git_safety.reason(item.arguments)
    if not reason:
        return ""
    if item.wrapper_depth:
        reason = f"shell wrapper contains {reason}"
    return f"{reason}.\n\nSegment: {shell_syntax.command_preview(item.raw)}"


def hides_verdict(item: shell_syntax.Command) -> bool:
    """Whether a run-time word could turn this command into one the guard would deny.

    A run-time word hides the verdict when it names the program or subcommand, sits among the
    arguments of a verb whose verdict depends on them, or picks the repository whose current branch
    an implicit push would update. Any other run-time word, such as a message or a path, cannot.
    """
    if not item.has_dynamic_words:
        return False
    if item.program_is_dynamic:
        return True
    name = Path(item.arguments[0]).name
    if name == "gh":
        return gh_hides_verdict(item)
    return name == "git" and git_hides_verdict(item)


def gh_hides_verdict(item: shell_syntax.Command) -> bool:
    subcommand_end = 2 if item.arguments[1:2] == ("api",) else 3
    return any(item.dynamic[1:subcommand_end]) or item.arguments[1:3] == ("pr", "merge")


def git_hides_verdict(item: shell_syntax.Command) -> bool:
    try:
        globals_, command = git_safety.git_arguments(item.arguments)
    except ValueError:
        return False
    start = 1 + len(globals_)
    if not command or item.dynamic[start]:
        return True
    verb = command[0]
    if verb == "push" and any(item.dynamic[1:start]) and git_safety.pushes_current_branch(command[1:]):
        return True
    if verb in git_safety.SUBCOMMAND_VERBS and len(command) > 1:
        return item.dynamic[start + 1] or (
            command[1] in git_safety.SUBCOMMAND_VERBS[verb] and any(item.dynamic[start + 2 :])
        )
    return verb in git_safety.OPTION_VERBS and any(item.dynamic[start + 1 :])


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
        audit_log.blocked(audit_log.Refusal("Bash", RULE))
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2
    return check(payload)


if __name__ == "__main__":
    sys.exit(main())
