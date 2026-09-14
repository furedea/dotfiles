#!/usr/bin/env -S python3 -IB
"""Summarize hook events without recording file bodies or command output."""

from datetime import UTC, datetime
import fcntl
import json
import os
from pathlib import Path
import sys


def summary(tool: str, values: dict, agent_summary: bool = True) -> str:
    """Retain only the established per-tool summary fields."""
    if tool == "Bash":
        return values.get("command") or ""
    if tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        return values.get("file_path") or ""
    if tool == "WebFetch":
        return values.get("url") or ""
    if tool == "Agent" and agent_summary:
        return f"{values.get('subagent_type') or 'general-purpose'}: {values.get('description') or ''}"
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))[:200]


def transcript_counts(path: str) -> dict[str, int]:
    """Count transcript records and tool uses while keeping their bodies out of logs."""
    counts = {"messages": 0, "tool_uses": 0}
    if not path:
        return counts
    try:
        with Path(path).open() as stream:
            for line in stream:
                counts["messages"] += 1
                try:
                    content = (json.loads(line).get("message") or {}).get("content") or []
                    counts["tool_uses"] += sum(
                        isinstance(item, dict) and item.get("type") == "tool_use" for item in content
                    )
                except ValueError, AttributeError, TypeError:
                    continue
    except OSError:
        pass
    return counts


def record(kind: str, payload: dict) -> dict | None:
    """Produce an audit record or explicitly ignore an unrelated lifecycle event."""
    defaults = {"tool": "PostToolUse", "denied": "PermissionDenied", "compaction": "PreCompact"}
    event = payload.get("hook_event_name") or defaults[kind]
    result = {
        "event": event,
        "status": "denied" if kind == "denied" else "observed",
        "session": payload.get("session_id") or "",
        "reason": payload.get("reason") or "" if kind == "denied" else "",
    }
    if kind == "compaction":
        source = payload.get("source") or ""
        if event != "PreCompact" and not (event == "SessionStart" and source in {"compact", "resume"}):
            return None
        path = payload.get("transcript_path") or ""
        result.update(
            tool="Compaction",
            input=path,
            transcript_path=path,
            counts=transcript_counts(path),
            trigger=payload.get("trigger") or "" if event == "PreCompact" else "",
            source=source if event == "SessionStart" else "",
        )
        return result
    tool = payload.get("tool_name") or ""
    value = summary(tool, payload.get("tool_input") or {}, kind != "denied")
    if kind == "tool" and (not tool or not value):
        return None
    result.update(tool=tool, input=value)
    return result


def append_record(entry: dict) -> None:
    """Append one locked JSONL record; observation failures must never block work."""
    try:
        now = datetime.now(UTC)
        entry = dict(entry, ts=now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        directory = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())) / "docs/logs/audit"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{now:%Y-%m-%d}.jsonl"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError, ValueError, TypeError:
        return


def blocked(tool: str, value: str, reason: str, hook: str, session: str) -> None:
    """Record a denial independently of the enforcement decision."""
    append_record(
        {
            "event": "Blocked",
            "status": "blocked",
            "tool": tool,
            "input": value,
            "reason": reason,
            "hook": hook,
            "session": session,
        }
    )


def main(arguments: list[str]) -> int:
    """Read an observational event without making logging an enforcement gate."""
    if len(arguments) != 1 or arguments[0] not in {"tool", "denied", "compaction"}:
        print("Usage: audit_events.py <tool|denied|compaction>", file=sys.stderr)
        return 1
    try:
        entry = record(arguments[0], json.load(sys.stdin))
        if entry is not None:
            append_record(entry)
    except ValueError, TypeError, AttributeError, OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
