#!/usr/bin/env -S python3 -IB
"""Evaluate generated prefixes and precise global/project command policy.

Deny prefixes and forbidden patterns stay hard denials. A command that reaches past the sandbox
in a form the precise allowlist does not list, or a command that cannot be inspected statically,
is handed to the user instead of being refused outright.
"""

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import audit_log
import command_policy
import hook_decision
from hook_decision import Verdict
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
) -> Verdict:
    """Judge one segment by its own words and by its canonical program and subcommand.

    Rules see only the command's words: redirections stay inside the sandbox, and heredoc bodies
    are data, not commands. The forbidden kind only denies: a literal deny prefix or pattern wins
    even beside a run-time argument. The allowed kind reviews only programs whose effects reach
    past the sandbox, such as GitHub writes and remote fetches, and lets every other program take
    any form, since the sandbox confines it. A run-time word in a governed program counts as a plain
    placeholder, so it passes only where any value would.
    """
    preview = shell_syntax.command_preview(item.raw)
    if kind == "forbidden":
        matched = command_policy.regex_reason(item.words_text, rules) or command_policy.regex_reason(
            candidate.words_text, rules
        )
        reason = command_policy.prefix_reason(candidate.arguments, prefixes, "deny") or matched
        if not reason:
            return hook_decision.ALLOW
        return hook_decision.deny(
            f"BLOCKED: forbidden command: {reason}.\n\nCommand: {preview}\n\n{hook_decision.REVIEW_HINT}"
        )
    if candidate.program_is_dynamic or candidate.arguments[0] not in command_policy.governed_programs(rules):
        return hook_decision.ALLOW
    governed = command_policy.prefix_rule(candidate.arguments, prefixes, "allow")
    if governed is None or command_policy.regex_reason(candidate.static_words_text, rules):
        return hook_decision.ALLOW
    prefix = " ".join(governed["prefix"])
    return hook_decision.ask(
        f"Needs review: command not in allowlist. '{prefix}' is approved, but not in this form.\n\nCommand: {preview}",
        prefix,
    )


def decide(kind: str, payload: dict, directory: Path = ROOT) -> Verdict:
    """Decide for an already decoded provider payload, recording every denial and escalation."""
    command = ""
    try:
        prefixes, rules = policies(kind, directory)
        if not isinstance(payload, dict):
            raise ValueError("failed to parse tool input JSON: expected an object")
        command = payload.get("tool_input", {}).get("command") or ""
        try:
            commands = shell_syntax.parse(command)
        except shell_syntax.UnsupportedSyntax as error:
            preview = shell_syntax.command_preview(command)
            verdict = hook_decision.ask(f"Needs review: {error}.\n\nCommand: {preview}", "syntax")
        else:
            verdicts = (objection(kind, item, command_policy.canonical(item), prefixes, rules) for item in commands)
            verdict = next((item for item in verdicts if item.decision != "allow"), hook_decision.ALLOW)
    except (ValueError, TypeError, AttributeError, OSError) as error:
        prefix = "forbidden command: " if kind == "forbidden" else ""
        verdict = hook_decision.deny(f"BLOCKED: {prefix}{error}\n\n{hook_decision.REVIEW_HINT}")
    record(kind, verdict, command, payload)
    return verdict


def record(kind: str, verdict: Verdict, command: str, payload: object) -> None:
    if verdict.decision == "allow":
        return
    context = payload if isinstance(payload, dict) else None
    session = payload.get("session_id", "") if isinstance(payload, dict) else ""
    writer = audit_log.blocked if verdict.decision == "deny" else audit_log.escalated
    writer(
        "Bash", command, verdict.reason, f"guard_{kind}_commands.sh", session, payload=context, detail=verdict.detail
    )


def check(kind: str, payload: dict, directory: Path = ROOT) -> int:
    """Enforce command policy for an already decoded provider payload."""
    return hook_decision.emit(decide(kind, payload, directory))


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
