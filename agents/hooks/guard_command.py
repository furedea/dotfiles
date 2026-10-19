#!/usr/bin/env -S python3 -IB
"""Evaluate generated prefixes and precise global/project command policy.

Deny prefixes and forbidden patterns stay hard denials. A command that reaches past the sandbox
in a form the precise allowlist does not list, or a command that cannot be inspected statically,
is handed to the user instead of being refused outright.
"""

from dataclasses import dataclass
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
import removal_policy
import request_policy
import shell_syntax


@dataclass(frozen=True, slots=True)
class Policy:
    """Generated permission prefixes beside the regex rules of one guard kind."""

    prefixes: list[dict]
    rules: list[dict]


@dataclass(frozen=True, slots=True)
class Attempt:
    """What an audit record names: the guard kind, the inspected command, and the raw payload."""

    kind: str
    command: str
    payload: object


def policies(kind: str, directory: Path) -> Policy:
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
    return Policy(prefixes, rules)


def objection(kind: str, item: shell_syntax.Command, policy: Policy) -> Verdict:
    """Judge one segment by its own words and by its canonical program and subcommand.

    Rules see only the command's words: redirections stay inside the sandbox, and heredoc bodies
    are data, not commands, and so is an argument containing whitespace.
    """
    candidate = command_policy.canonical(item)
    preview = shell_syntax.command_preview(item.raw)
    if kind == "forbidden":
        return forbidden_objection(item, candidate, policy)
    if item.in_function and (item.program_is_dynamic or runs_sensitive_program(candidate, policy)):
        return hook_decision.ask(
            f"Needs review: a function body runs {candidate.arguments[0]}, whose calls cannot be judged form by form."
            f"\n\nCommand: {preview}",
            "function",
        )
    if not candidate.program_is_dynamic and candidate.arguments[0] in request_policy.PROGRAMS:
        return request_objection(candidate, preview)
    return governed_objection(candidate, policy, preview)


def forbidden_objection(item: shell_syntax.Command, candidate: shell_syntax.Command, policy: Policy) -> Verdict:
    """Deny only: a literal deny prefix or pattern wins even beside a run-time argument."""
    rules = policy.rules
    matched = command_policy.regex_reason(item.command_words_text, rules) or command_policy.regex_reason(
        candidate.command_words_text, rules
    )
    reason = command_policy.prefix_reason(candidate.arguments, policy.prefixes, "deny") or matched
    if not reason:
        return hook_decision.ALLOW
    preview = shell_syntax.command_preview(item.raw)
    return hook_decision.deny(
        f"BLOCKED: forbidden command: {reason}.\n\nCommand: {preview}\n\n{hook_decision.REVIEW_HINT}"
    )


def governed_objection(candidate: shell_syntax.Command, policy: Policy, preview: str) -> Verdict:
    """Review only programs whose effects reach past the sandbox; the sandbox confines every other form.

    A run-time word counts as a plain placeholder, so it passes only where any value would, and a
    command that can hide an option from the rules, or takes more arguments from xargs, asks.
    """
    prefixes, rules = policy.prefixes, policy.rules
    if candidate.program_is_dynamic or candidate.arguments[0] not in command_policy.governed_programs(rules):
        return hook_decision.ALLOW
    governed = command_policy.prefix_rule(candidate.arguments, prefixes, "allow")
    if governed is None or (
        not candidate.appends_input
        and not candidate.hides_options
        and command_policy.regex_reason(command_policy.judged_text(candidate), rules)
    ):
        return hook_decision.ALLOW
    prefix = " ".join(governed["prefix"])
    return hook_decision.ask(
        f"Needs review: command not in allowlist. '{prefix}' is approved, but not in this form.\n\nCommand: {preview}",
        prefix,
    )


def runs_sensitive_program(candidate: shell_syntax.Command, policy: Policy) -> bool:
    sensitive = command_policy.sensitive_programs(policy.prefixes, policy.rules) | request_policy.PROGRAMS.keys()
    return candidate.arguments[0] in sensitive


def request_objection(candidate: shell_syntax.Command, preview: str) -> Verdict:
    """Pass a curl or wget call whose decoded, literal arguments stay on this machine; ask for any other."""
    if (
        not candidate.appends_input
        and not candidate.has_dynamic_words
        and request_policy.is_local(candidate.arguments)
    ):
        return hook_decision.ALLOW
    return hook_decision.ask(f"{request_policy.REMOTE_REASON}\n\nCommand: {preview}", candidate.arguments[0])


def removal_objection(kind: str, item: shell_syntax.Command, workspace: removal_policy.Workspace) -> Verdict:
    """Pass rm where a temporary directory or Git accounts for its targets; else deny a tree and ask for files."""
    removal = removal_policy.removal(command_policy.canonical(item), workspace)
    if removal is None or removal.is_accounted_for:
        return hook_decision.ALLOW
    preview = shell_syntax.command_preview(item.raw)
    if kind == "allowed":
        return hook_decision.ask(f"Needs review: {removal_policy.FILE_REASON}.\n\nCommand: {preview}", "rm")
    if not removal.removes_unaccounted_tree:
        return hook_decision.ALLOW
    return hook_decision.deny(
        f"BLOCKED: forbidden command: {removal_policy.TREE_REASON}\n\nCommand: {preview}\n\n{hook_decision.REVIEW_HINT}"
    )


def decide(kind: str, payload: dict, directory: Path = ROOT) -> Verdict:
    """Decide for an already decoded provider payload, recording every denial and escalation."""
    command = ""
    try:
        policy = policies(kind, directory)
        if not isinstance(payload, dict):
            raise ValueError("failed to parse tool input JSON: expected an object")
        command = payload.get("tool_input", {}).get("command") or ""
        try:
            commands = shell_syntax.parse(command)
        except shell_syntax.UnsupportedSyntax as error:
            preview = shell_syntax.command_preview(command)
            verdict = hook_decision.ask(f"Needs review: {error}.\n\nCommand: {preview}", "syntax")
        else:
            workspace = removal_policy.workspace(payload, commands)
            verdicts = (
                verdict
                for item in commands
                for verdict in (objection(kind, item, policy), removal_objection(kind, item, workspace))
            )
            verdict = next((item for item in verdicts if item.decision != "allow"), hook_decision.ALLOW)
    except (ValueError, TypeError, AttributeError, OSError) as error:
        prefix = "forbidden command: " if kind == "forbidden" else ""
        verdict = hook_decision.deny(f"BLOCKED: {prefix}{error}\n\n{hook_decision.REVIEW_HINT}")
    record(verdict, Attempt(kind, command, payload))
    return verdict


def record(verdict: Verdict, attempt: Attempt) -> None:
    if verdict.decision == "allow":
        return
    payload = attempt.payload
    context = payload if isinstance(payload, dict) else None
    session = payload.get("session_id", "") if isinstance(payload, dict) else ""
    writer = audit_log.blocked if verdict.decision == "deny" else audit_log.escalated
    writer(
        audit_log.Refusal("Bash", f"guard_{attempt.kind}_commands.sh", session, payload=context, detail=verdict.detail)
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
        audit_log.blocked(audit_log.Refusal("Bash", f"guard_{arguments[0]}_commands.sh"))
        print("BLOCKED: failed to parse tool input JSON", file=sys.stderr)
        return 2
    return check(arguments[0], payload)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
