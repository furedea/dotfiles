#!/usr/bin/env -S python3 -IB
"""Evaluate generated prefixes and precise global/project command policy.

Deny prefixes and forbidden patterns stay hard denials. A command that reaches past the sandbox
in a form the precise allowlist does not list, or a command that cannot be inspected statically,
is handed to the user instead of being refused outright.
"""

from dataclasses import dataclass, replace
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
import herdr_grammar
import hook_decision
from hook_decision import Verdict
import shell_syntax


REQUEST_PROGRAMS = frozenset({"curl", "wget"})
REMOTE_REASON = (
    "Needs review: remote curl/wget can send local data. Read web pages with the web-fetch tool, "
    "or use gh api / nix store prefetch-file for exact values and files."
)
# Settings that can send a request to a local server somewhere else: a proxy, or another configuration file.
# The only programs the literal_words rules govern; through any wrapper they get main's rules, or no
# rule at all for curl and wget.
LITERAL_PROGRAMS = frozenset({"curl", "gh", "herdr", "wget"})
# Characters through which any shell may expand or run something; a command holding one anywhere
# outside single quotes, in the program name, an assignment, or a redirect included, gets no
# literal_words rule.
EXPANDING_TEXT = re.compile(r"[$`~*?\[\]{}]|\\\n")
REQUEST_SETTINGS = re.compile(r"proxy|curlrc|wgetrc|curl_home|(^|[^a-z0-9_])(home|xdg_config_home)=", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Policy:
    """Generated permission prefixes beside the regex rules of one guard kind.

    `literal_words` is False when the command may not use the rules marked literal_words; those rules
    still count toward the programs the allowed kind governs.
    """

    prefixes: list[dict]
    rules: list[dict]
    literal_words: bool = True

    @property
    def listing_rules(self) -> list[dict]:
        return self.rules if self.literal_words else command_policy.literal_rules(self.rules, literal=False)


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


def is_listed(candidate: shell_syntax.Command, rules: list[dict]) -> bool:
    """Whether a rule lists the form; Herdr's watching commands must also keep to their documented options."""
    if not command_policy.regex_reason(candidate.static_words_text, rules):
        return False
    return not herdr_grammar.is_watch_command(candidate.arguments) or herdr_grammar.is_documented(candidate.arguments)


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
    if candidate.arguments[0] == "herdr" and herdr_grammar.has_global_option(candidate.arguments):
        return hook_decision.ask(
            f"Needs review: a Herdr global option such as --session shifts the words after it.\n\nCommand: {preview}",
            "herdr",
        )
    governed = command_policy.prefix_rule(candidate.arguments, prefixes, "allow")
    if governed is None or (
        not candidate.appends_input and not candidate.hides_options and is_listed(candidate, policy.listing_rules)
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


def decide(kind: str, payload: dict, directory: Path = ROOT) -> Verdict:
    """Decide for an already decoded provider payload, recording every denial and escalation."""
    try:
        policy = policies(kind, directory)
        if not isinstance(payload, dict):
            raise ValueError("failed to parse tool input JSON: expected an object")
        verdict = command_verdict(kind, payload, policy)
    except (ValueError, TypeError, AttributeError, OSError) as error:
        prefix = "forbidden command: " if kind == "forbidden" else ""
        verdict = hook_decision.deny(f"BLOCKED: {prefix}{error}\n\n{hook_decision.REVIEW_HINT}")
    record(verdict, kind, payload)
    return verdict


def command_verdict(kind: str, payload: dict, policy: Policy) -> Verdict:
    """The first objection any segment raises, then whether the command's settings could redirect a request.

    Rules marked literal_words apply only when the whole command is one plain gh, herdr, curl, or wget
    call whose text, outside single quotes, holds nothing a shell expands.
    """
    command = payload.get("tool_input", {}).get("command") or ""
    try:
        commands = shell_syntax.parse(command)
    except shell_syntax.UnsupportedSyntax as error:
        preview = shell_syntax.command_preview(command)
        return hook_decision.ask(f"Needs review: {error}.\n\nCommand: {preview}", "syntax")
    if not allows_literal_rules(command, commands):
        policy = replace(policy, literal_words=False)
    verdicts = (objection(kind, item, policy) for item in commands)
    verdict = next((item for item in verdicts if item.decision != "allow"), hook_decision.ALLOW)
    if kind == "allowed" and verdict.decision == "allow":
        return settings_objection(command, commands)
    return verdict


def allows_literal_rules(command: str, commands: tuple[shell_syntax.Command, ...]) -> bool:
    """Whether the command is exactly one plain gh, herdr, curl, or wget call with nothing expanding outside single
    quotes: no list, pipe, compound, wrapper, eval, or nested script; when unsure, it is not."""
    if len(commands) != 1 or Path(commands[0].arguments[0]).name not in LITERAL_PROGRAMS:
        return False
    try:
        if not shell_syntax.is_one_simple_command(command):
            return False
        return not EXPANDING_TEXT.search(command) or not EXPANDING_TEXT.search(
            shell_syntax.text_outside_single_quotes(command)
        )
    except shell_syntax.UnsupportedSyntax:
        return False


def record(verdict: Verdict, kind: str, payload: object) -> None:
    if verdict.decision == "allow":
        return
    context = payload if isinstance(payload, dict) else None
    session = payload.get("session_id", "") if isinstance(payload, dict) else ""
    writer = audit_log.blocked if verdict.decision == "deny" else audit_log.escalated
    writer(audit_log.Refusal("Bash", f"guard_{kind}_commands.sh", session, payload=context, detail=verdict.detail))


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
