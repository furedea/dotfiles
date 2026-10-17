#!/usr/bin/env -S python3 -IB
"""Replay recently run Bash commands through the command hooks and count their verdicts.

Commands come from Claude transcripts and Codex session logs. They are judged, never run, and the
audit log is left alone. Command text goes to the terminal only: transcripts hold command bodies
that must not be copied into files or GitHub.

Usage: replay_commands.py --since YYYY-MM-DD[THH:MM] [--hooks DIR]
"""

import argparse
from collections import Counter
from collections.abc import Callable, Iterator
from compression import zstd
from dataclasses import dataclass
from datetime import datetime
from importlib import util
import json
import os
from pathlib import Path
import shlex
import sys
from types import ModuleType
from typing import Any, TextIO


DECISIONS = ("allow", "ask", "deny")
SINCE_FORMATS = ("%Y-%m-%d", "%Y-%m-%dT%H:%M")
SHELL_FLAGS = frozenset({"-c", "-lc"})
SHELLS = frozenset({"bash", "sh", "zsh"})
EXCERPT_LIMIT = 200


@dataclass(frozen=True, slots=True)
class RecordedCommand:
    command: str
    cwd: str


@dataclass(frozen=True, slots=True)
class Judgment:
    decision: str
    reason: str
    command: str


def main(arguments: list[str]) -> int:
    options = parser().parse_args(arguments)
    home = Path.home()
    commands = [*claude_commands(home, options.since), *codex_commands(home, options.since)]
    replayer = Replayer(options.hooks.resolve())
    print(report(options.since, [replayer.judge(command) for command in commands]))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Replay recent Bash commands through the command hooks.")
    result.add_argument("--since", required=True, type=since_time, help="YYYY-MM-DD[THH:MM], local time")
    result.add_argument("--hooks", type=Path, default=Path(__file__).resolve().parent, help="hooks directory")
    return result


def since_time(value: str) -> datetime:
    for pattern in SINCE_FORMATS:
        try:
            return datetime.strptime(value, pattern).astimezone()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD[THH:MM], got {value!r}")


def claude_commands(home: Path, since: datetime) -> Iterator[RecordedCommand]:
    """Bash tool calls the assistant made in each session transcript."""
    for path in sorted(home.glob(".claude/projects/*/*.jsonl")):
        for entry in log_entries(path, since):
            if entry.get("type") == "assistant" and is_recent(entry, since):
                cwd = text(entry.get("cwd"))
                yield from (RecordedCommand(command, cwd) for command in bash_tool_uses(entry))


def bash_tool_uses(entry: dict) -> list[str]:
    content = mapping(entry.get("message")).get("content")
    blocks = [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []
    calls = [block for block in blocks if block.get("type") == "tool_use" and block.get("name") == "Bash"]
    return [command for call in calls if (command := text(mapping(call.get("input")).get("command")))]


def codex_commands(home: Path, since: datetime) -> Iterator[RecordedCommand]:
    """Shell calls in Codex rollouts: exec_command calls in older logs, completed command items in newer ones."""
    for path in sorted(home.glob(".codex/sessions/**/*.jsonl*")):
        if path.suffix not in {".jsonl", ".zst"}:
            continue
        session_cwd = ""
        for entry in log_entries(path, since):
            payload = mapping(entry.get("payload"))
            if entry.get("type") in {"session_meta", "turn_context"}:
                session_cwd = text(payload.get("cwd")) or session_cwd
            if (recorded := codex_call(payload, session_cwd)) and is_recent(entry, since):
                yield recorded


def codex_call(payload: dict, session_cwd: str) -> RecordedCommand | None:
    if payload.get("type") == "function_call" and payload.get("name") == "exec_command":
        try:
            arguments = mapping(json.loads(text(payload.get("arguments"))))
        except ValueError:
            return None
        command = text(arguments.get("cmd"))
        return RecordedCommand(command, text(arguments.get("workdir")) or session_cwd) if command else None
    item = mapping(payload.get("item"))
    if payload.get("type") != "item_completed" or item.get("type") != "CommandExecution":
        return None
    command = shell_script(item.get("command"))
    return RecordedCommand(command, text(item.get("cwd")) or session_cwd) if command else None


def shell_script(command: object) -> str:
    """The script a login shell ran, since the hooks judge the script, not the shell that wraps it."""
    if isinstance(command, str):
        return command
    if not isinstance(command, list) or not all(isinstance(word, str) for word in command):
        return ""
    if len(command) == 3 and Path(command[0]).name in SHELLS and command[1] in SHELL_FLAGS:
        return command[2]
    return shlex.join(command)


def log_entries(path: Path, since: datetime) -> Iterator[dict]:
    """Decode one JSON object per line, skipping logs last written before the period starts."""
    if path.stat().st_mtime < since.timestamp():
        return
    try:
        with open_log(path) as stream:
            for line in stream:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    yield entry
    except (OSError, EOFError, zstd.ZstdError) as error:
        print(f"skipped the rest of {path}: {error}", file=sys.stderr)


def open_log(path: Path) -> TextIO:
    if path.suffix == ".zst":
        return zstd.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open(encoding="utf-8", errors="replace")


def is_recent(entry: dict, since: datetime) -> bool:
    try:
        timestamp = datetime.fromisoformat(text(entry.get("timestamp")))
    except ValueError:
        return False
    return timestamp.tzinfo is not None and timestamp >= since


class Replayer:
    """Judge commands with one hooks directory's guards, in the order the PreToolUse hooks run."""

    def __init__(self, hooks: Path) -> None:
        use_checkout_permissions(hooks)
        command_guard = load(hooks, "guard_command")
        git_guard = load(hooks, "guard_git")
        silence(sys.modules["audit_log"])
        self.guards: tuple[tuple[str, Callable[[dict], Any]], ...] = (
            ("forbidden", lambda payload: command_guard.decide("forbidden", payload)),
            ("git", git_guard.decide),
            ("allowed", lambda payload: command_guard.decide("allowed", payload)),
        )

    def judge(self, recorded: RecordedCommand) -> Judgment:
        """Return the first guard's objection, or allow when every guard lets the command pass."""
        # Project rules belong to the directory the command ran in; an unknown one has none.
        os.environ["AGENT_PROJECT_DIR"] = recorded.cwd or os.devnull
        payload = {"tool_name": "Bash", "tool_input": {"command": recorded.command}, "cwd": recorded.cwd}
        for name, decide in self.guards:
            verdict = decide(payload)
            if verdict.decision != "allow":
                summary = verdict.detail or next(iter(verdict.reason.splitlines()), "")
                return Judgment(verdict.decision, f"{name}: {summary}", recorded.command)
        return Judgment("allow", "", recorded.command)


def use_checkout_permissions(hooks: Path) -> None:
    """A checkout keeps the generated prefix list beside its hooks directory, not among the rules."""
    checkout = hooks.parent / "command_permissions.json"
    if not (hooks / "rules/command_permissions.json").is_file() and checkout.is_file():
        os.environ.setdefault("AGENT_COMMAND_PERMISSIONS", str(checkout))


def load(hooks: Path, name: str) -> ModuleType:
    spec = util.spec_from_file_location(name, hooks / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {hooks}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def silence(audit_log: ModuleType) -> None:
    """Replayed verdicts are measurements, not refusals, so they stay out of the audit log."""
    for writer in ("blocked", "escalated"):
        setattr(audit_log, writer, lambda *_, **__: None)


def report(since: datetime, judgments: list[Judgment]) -> str:
    decisions = Counter(judgment.decision for judgment in judgments)
    objections = sorted((judgment for judgment in judgments if judgment.decision != "allow"), key=objection_key)
    reasons = Counter(objection_key(judgment) for judgment in objections)
    lines = [f"Replayed {len(judgments)} commands since {since:%Y-%m-%dT%H:%M}", ""]
    lines += [f"  {decision:<5} {decisions[decision]}" for decision in DECISIONS]
    lines += ["", "Reasons"]
    lines += [f"  {decision:<5} {count:>5}  {reason}" for (decision, reason), count in sorted(reasons.items())]
    lines += ["", "Asked and denied commands"]
    for judgment in objections:
        lines += [f"  {judgment.decision:<5} {judgment.reason}", f"    {excerpt(judgment.command)}"]
    return "\n".join(lines)


def objection_key(judgment: Judgment) -> tuple[str, str]:
    return judgment.decision, judgment.reason


def excerpt(command: str) -> str:
    lines = command.splitlines() or [""]
    first = lines[0][:EXCERPT_LIMIT]
    more = len(lines) - 1
    return f"{first} (+{more} more lines)" if more else first


def mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def text(value: object) -> str:
    return value if isinstance(value, str) else ""


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
