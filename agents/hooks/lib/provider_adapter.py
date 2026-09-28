"""Translate provider hook payloads at the boundary to shared hook implementations.

Each provider adapter declares only a Profile of provider facts. Payload normalization,
guard dispatch, and CLI validation live here so the providers cannot drift apart.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys

import audit_log
import guard_command
import guard_file
import guard_git
import hook_dispatch
import hook_input
import lint_format
import patch_input
import secret_path_policy
import shell_syntax
import verification_session


SECRET_PATH_RULE = "guard_secret_paths.sh"
SHELL_MODES = ("allowed", "forbidden", "git", "commit")
PATH_MODES = ("command", "patch")
AUDIT_KINDS = ("tool", "compaction")
CONTENT_MODES = ("prompt", "read", "write", "apply-patch")
NO_ARGUMENT: tuple[str, ...] = ()
ANY_ARGUMENT = None
Formatter = Callable[[str, dict], dict]


def denial(result: dict) -> dict | None:
    """Return the block decision for a shared Claude-shaped denial, if the result is one."""
    specific = result.get("hookSpecificOutput")
    if not isinstance(specific, dict) or specific.get("permissionDecision") != "deny":
        return None
    return {"decision": "block", "reason": specific.get("permissionDecisionReason") or "Blocked by hook policy"}


def system_message(event: str, result: dict) -> dict:
    """Format a shared result for providers that surface a top-level systemMessage."""
    message = result.get("systemMessage")
    return denial(result) or ({"systemMessage": message} if message else result)


def additional_context(event: str, result: dict) -> dict:
    """Format a shared result for providers that surface messages as additionalContext."""
    message = result.get("systemMessage")
    context = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}
    return denial(result) or (context if message else result)


def no_cwd() -> str:
    return ""


@dataclass(frozen=True)
class Profile:
    """Provider facts the shared adapter needs; every behavior derived from them is shared.

    `events` maps verification events to native event names and enables `native`.
    `compaction_events` maps native event names to shared audit event names and enables `audit`.
    `manifest_env` names the manifest override and enables `dispatch`.
    """

    name: str
    tools: Mapping[str, str] = field(default_factory=dict)
    events: Mapping[str, str] = field(default_factory=dict)
    compaction_events: Mapping[str, str] = field(default_factory=dict)
    formatter: Formatter = system_message
    content_modes: tuple[str, ...] = CONTENT_MODES
    cwd_fallback: Callable[[], str] = os.getcwd
    manifest_env: str = ""
    manifest_default: str = ""


class Adapter:
    """Run one provider's hook commands against the shared hook implementations."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def main(self, arguments: list[str]) -> int:
        kind, rest = (arguments[0], arguments[1:]) if arguments else ("", [])
        if not self._accepts(kind, rest):
            print(f"Usage: hook_adapter.py <{self._usage()}>", file=sys.stderr)
            return 1
        try:
            return self.dispatch(kind, rest, self._payload())
        except (OSError, ValueError, TypeError, AttributeError) as error:
            print(f"BLOCKED: {error}", file=sys.stderr)
            return 2

    def dispatch(self, kind: str, arguments: list[str], payload: dict) -> int:
        if kind == "lint":
            return self.lint(payload)
        if kind == "harness":
            return self.harness(payload)
        commands = {
            "native": self.native,
            "audit": self.audit,
            "dispatch": self.fan_out,
            "shell": self.shell,
            "paths": self.check_paths,
            "content": self.content,
        }
        return commands[kind](arguments[0], payload)

    def normalized(self, payload: dict) -> dict:
        """Copy the provider payload, adding the shared fields and canonical tool name."""
        result = dict(payload)
        result["tool_input"] = tool_input(payload)
        result.setdefault("cwd", self.profile.cwd_fallback())
        result.setdefault("prompt", payload.get("text") or "")
        result["provider"] = self.profile.name
        if canonical := self.profile.tools.get(payload.get("tool_name") or ""):
            result["tool_name"] = canonical
        return result

    def translated(self, payload: dict, tool: str, values: dict) -> dict:
        """Forward only the fields a shared guard reads, under the shared tool name."""
        return {
            "tool_name": tool,
            "tool_input": values,
            "session_id": payload.get("session_id") or "",
            "cwd": payload.get("cwd") or self.profile.cwd_fallback(),
            "provider": self.profile.name,
        }

    def native(self, event: str, payload: dict) -> int:
        context = self.normalized(payload)
        try:
            result = verification_session.dispatch(self.profile.name, event, context)
        except (OSError, ValueError, TypeError, KeyError) as error:
            result = verification_session.failure(event, context, error)
        output = self.profile.formatter(self.profile.events[event], result)
        print(json.dumps(output, ensure_ascii=True, separators=(",", ":")))
        return 0

    def audit(self, kind: str, payload: dict) -> int:
        context = self.normalized(payload)
        if kind == "compaction":
            context = self._compaction_context(context)
        if context is not None:
            audit_log.append_record(
                audit_log.record(kind, context, self.profile.name), cwd=Path(context["cwd"] or ".")
            )
        return 0

    def fan_out(self, event: str, payload: dict) -> int:
        return hook_dispatch.run(self._manifest(), event, payload)

    def shell(self, mode: str, payload: dict) -> int:
        values = {"command": command_text(self.normalized(payload)["tool_input"])}
        command = self.translated(payload, "Bash", values)
        if mode == "git":
            return guard_git.check(command)
        if mode == "commit":
            return guard_file.check("commit", command, shared_directory())
        return guard_command.check(mode, command, shared_directory())

    def lint(self, payload: dict) -> int:
        """Report shared quality diagnostics using the PostToolUse JSON contract."""
        lint_format.emit(lint_format.diagnostics(self.normalized(payload)))
        return 0

    def harness(self, payload: dict) -> int:
        for name in edit_targets(self.normalized(payload)):
            absolute = name if name.startswith(("/", "~/")) else str(Path.cwd() / name)
            values = {"file_path": absolute}
            if status := guard_file.check(
                "harness", self.translated(payload, "apply_patch", values), shared_directory()
            ):
                return status
        return 0

    def check_paths(self, mode: str, payload: dict) -> int:
        rules = secret_path_policy.load(secret_policy_path())
        context = self.normalized(payload)
        candidates = edit_targets(context) if mode == "patch" else shell_words(command_text(context["tool_input"]))
        for value in candidates:
            if rule := secret_path_policy.blocked_rule(value, rules):
                deny_secret_path(mode, value, rule, context)
        return 0

    def content(self, mode: str, payload: dict) -> int:
        context = self.normalized(payload)
        if mode != "apply-patch":
            return guard_file.check(mode, context, shared_directory())
        body = hook_input.patch_body(context["tool_input"], context.get("tool_name") or "apply_patch")
        values = {"content": patch_input.added_text(body)}
        return guard_file.check("write", self.translated(payload, "Edit", values), shared_directory())

    def _compaction_context(self, context: dict) -> dict | None:
        """Name a native compaction event as shared audit expects, or drop an unknown event."""
        event = self.profile.compaction_events.get(context.get("hook_event_name") or "")
        return None if event is None else context | {"hook_event_name": event}

    def _manifest(self) -> Path:
        default = Path.home() / self.profile.manifest_default
        return Path(os.environ.get(self.profile.manifest_env, str(default)))

    def _payload(self) -> dict:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise TypeError("hook payload must be an object")
        cwd = payload.get("cwd") or self.profile.cwd_fallback()
        if isinstance(cwd, str) and cwd:
            os.chdir(cwd)
        return payload

    def _accepts(self, kind: str, rest: list[str]) -> bool:
        commands = self._commands()
        if kind not in commands or any(value in {"-h", "--help"} for value in rest):
            return False
        choices = commands[kind]
        if choices == NO_ARGUMENT:
            return not rest
        return len(rest) == 1 and (choices is ANY_ARGUMENT or rest[0] in choices)

    def _commands(self) -> dict[str, tuple[str, ...] | None]:
        """Map each accepted command to its argument choices."""
        commands: dict[str, tuple[str, ...] | None] = {}
        if self.profile.events:
            commands["native"] = tuple(self.profile.events)
        if self.profile.compaction_events:
            commands["audit"] = AUDIT_KINDS
        if self.profile.manifest_env:
            commands["dispatch"] = ANY_ARGUMENT
        return commands | {
            "shell": SHELL_MODES,
            "lint": NO_ARGUMENT,
            "harness": NO_ARGUMENT,
            "paths": PATH_MODES,
            "content": self.profile.content_modes,
        }

    def _usage(self) -> str:
        return "|".join(usage_entry(kind, choices) for kind, choices in self._commands().items())


def shared_directory() -> Path:
    return Path(os.environ.get("AGENT_HARNESS_ROOT", str(Path.home()))) / ".claude/hooks"


def secret_policy_path() -> Path:
    default = shared_directory() / "rules/secret_path_policy.json"
    return Path(os.environ.get("AGENT_SECRET_PATH_POLICY", str(default)))


def tool_input(payload: dict) -> object:
    """Copy the tool arguments; a non-object is kept so the consuming check rejects it."""
    values = payload.get("tool_input")
    if values is None:
        # Hermes carries tool arguments in `args`.
        values = payload.get("args")
    if not isinstance(values, dict):
        return {} if values is None else values
    result = dict(values)
    if name := hook_input.file_path(values):
        result["file_path"] = name
    return result


def command_text(values: dict) -> str:
    return values.get("command") or values.get("cmd") or ""


def edit_targets(context: dict) -> list[str]:
    values = context["tool_input"]
    body = hook_input.patch_body(values, context.get("tool_name"))
    return [name for name in (hook_input.file_path(values), *patch_input.paths(body)) if name]


def shell_words(command: str) -> list[str]:
    """Return every argument and redirection word, plus the values of assignment words."""
    try:
        commands = shell_syntax.parse(command)
    except shell_syntax.UnsupportedSyntax as error:
        raise ValueError(f"{error}\n\nCommand: {shell_syntax.command_preview(command)}") from error
    words = [word for item in commands for word in (*item.arguments, *item.redirections)]
    return words + [word.partition("=")[2] for word in words if "=" in word]


def deny_secret_path(mode: str, value: str, rule: dict, context: dict) -> None:
    command = mode == "command"
    audit_log.blocked(
        "Bash" if command else "apply_patch",
        command_text(context["tool_input"]) if command else value,
        f"{rule['reason']}: {value}",
        SECRET_PATH_RULE,
        context.get("session_id") or "",
        payload=context,
        targets=() if command else (value,),
    )
    raise ValueError(
        f"secret path policy matched.\n\nPath: {value}\nPattern: {rule['pattern']}\n\nWhy:\n  {rule['reason']}"
    )


def usage_entry(kind: str, choices: tuple[str, ...] | None) -> str:
    if choices is ANY_ARGUMENT:
        return f"{kind} <event>"
    return f"{kind} {'/'.join(choices)}" if choices else kind
