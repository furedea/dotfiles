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
import re
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import audit_log
import command_policy
import hook_decision
from hook_decision import Verdict
import removal_policy
import shell_syntax


REQUEST_PROGRAMS = frozenset({"curl", "wget"})
REMOTE_REASON = (
    "Needs review: remote curl/wget can send local data. Read web pages with the web-fetch tool, "
    "or use gh api / nix store prefetch-file for exact values and files."
)
# Settings that can send a request to a local server somewhere else: a proxy, or another configuration file.
REQUEST_SETTINGS = re.compile(r"proxy|curlrc|wgetrc|curl_home|(^|[^a-z0-9_])(home|xdg_config_home)=", re.IGNORECASE)


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
    command that can hide an option from the rules, or takes more arguments from xargs, asks: a
    quoted option, or a word that may split into several, such as an unquoted expansion.
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
    if candidate.arguments[0] in REQUEST_PROGRAMS:
        return hook_decision.ask(f"{REMOTE_REASON}\n\nCommand: {preview}", prefix)
    return hook_decision.ask(
        f"Needs review: command not in allowlist. '{prefix}' is approved, but not in this form.\n\nCommand: {preview}",
        prefix,
    )


def settings_objection(command: str, commands: tuple[shell_syntax.Command, ...]) -> Verdict:
    """Ask when a curl or wget call shares its command with settings that could send it elsewhere."""
    requests = any(command_policy.canonical(item).arguments[0] in REQUEST_PROGRAMS for item in commands)
    if not requests or not REQUEST_SETTINGS.search(command):
        return hook_decision.ALLOW
    return hook_decision.ask(f"{REMOTE_REASON}\n\nCommand: {shell_syntax.command_preview(command)}", "settings")


def removal_objection(kind: str, item: shell_syntax.Command, settled: bool) -> Verdict:
    """Pass rm where a temporary directory or Git accounts for its targets; else deny a tree and ask for files."""
    removal = removal_policy.removal(command_policy.canonical(item), settled)
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
        verdict = command_verdict(kind, payload, policy)
    except (ValueError, TypeError, AttributeError, OSError) as error:
        prefix = "forbidden command: " if kind == "forbidden" else ""
        verdict = hook_decision.deny(f"BLOCKED: {prefix}{error}\n\n{hook_decision.REVIEW_HINT}")
    record(verdict, Attempt(kind, command, payload))
    return verdict


def command_verdict(kind: str, payload: dict, policy: Policy) -> Verdict:
    """The first objection any segment raises, then whether the command's settings could redirect a request."""
    command = payload.get("tool_input", {}).get("command") or ""
    try:
        commands = shell_syntax.parse(command)
    except shell_syntax.UnsupportedSyntax as error:
        preview = shell_syntax.command_preview(command)
        return hook_decision.ask(f"Needs review: {error}.\n\nCommand: {preview}", "syntax")
    settled = removal_policy.is_settled(commands)
    verdicts = (
        verdict
        for item in commands
        for verdict in (objection(kind, item, policy), removal_objection(kind, item, settled))
    )
    verdict = next((item for item in verdicts if item.decision != "allow"), hook_decision.ALLOW)
    if kind == "allowed" and verdict.decision == "allow":
        return settings_objection(command, commands)
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
