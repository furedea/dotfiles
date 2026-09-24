#!/usr/bin/env -S python3 -IB
"""Record bounded hook metadata without retaining prompts, commands, or file bodies."""

from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time


SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(SCRIPT.parent / "lib"))

from session_store import file_lock, private_directory, worktree_id

import hook_input
import patch_input


RETENTION_SECONDS = 7 * 24 * 60 * 60
LOG_LIMIT_BYTES = 1024 * 1024
TOTAL_LOG_LIMIT_BYTES = 100 * LOG_LIMIT_BYTES
CLEANUP_INTERVAL_SECONDS = 60 * 60
MAX_TARGETS = 32
MAX_TARGET_LENGTH = 256
SAFE_LABEL = re.compile(r"[^A-Za-z0-9_.:-]+")
FILE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch"})


def _label(value: object, fallback: str = "unknown") -> str:
    if not isinstance(value, str) or not value:
        return fallback
    label = SAFE_LABEL.sub("_", value)[:64]
    return label or fallback


def _provider(payload: dict, explicit: str | None = None) -> str:
    candidate = explicit or payload.get("provider")
    if candidate in {"claude", "codex", "devin", "hermes", "pi"}:
        return candidate
    return "codex" if payload.get("turn_id") else "claude"


def _session(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "unknown"
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def _cwd(payload: dict) -> Path:
    value = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if not isinstance(value, str) or not value:
        return Path.cwd().resolve()
    try:
        return Path(value).expanduser().resolve()
    except OSError, RuntimeError:
        return Path.cwd().resolve()


def _worktree(cwd: Path) -> str:
    try:
        return worktree_id(cwd)
    except OSError, RuntimeError, ValueError:
        return hashlib.sha256(os.fsencode(str(cwd))).hexdigest()[:32]


def _target(value: object, cwd: Path) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if "://" in value or value.startswith(("data:", "mailto:")):
        return "external"
    try:
        path = Path(value).expanduser()
        resolved = (path if path.is_absolute() else cwd / path).resolve()
        relative = resolved.relative_to(cwd)
        result = relative.as_posix()
    except OSError, RuntimeError, ValueError:
        result = f"outside/{Path(value).name or 'unknown'}"
    return result[:MAX_TARGET_LENGTH]


def _targets(tool: str, values: dict, cwd: Path) -> list[str]:
    names: tuple[str, ...] = ()
    if tool == "apply_patch":
        command = values.get("command")
        if isinstance(command, str):
            names = patch_input.paths(command)
    elif tool in FILE_TOOLS:
        names = (name,) if (name := hook_input.file_path(values)) else ()
        edits = values.get("edits")
        if isinstance(edits, list):
            names += tuple(
                item["file_path"]
                for item in edits
                if isinstance(item, dict) and isinstance(item.get("file_path"), str)
            )
    result: list[str] = []
    for name in names:
        target = _target(name, cwd)
        if target is not None and target not in result:
            result.append(target)
        if len(result) >= MAX_TARGETS:
            break
    return result


def _duration(payload: dict) -> int | float | None:
    value = payload.get("duration_ms")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return value
    return None


def record(kind: str, payload: dict, provider: str | None = None) -> dict | None:
    """Produce a metadata-only audit record or ignore an unrelated lifecycle event."""
    if not isinstance(payload, dict):
        return None
    defaults = {"tool": "PostToolUse", "denied": "PermissionDenied", "compaction": "PreCompact"}
    event = _label(payload.get("hook_event_name") or defaults[kind])
    cwd = _cwd(payload)
    result = {
        "event": event,
        "status": "denied" if kind == "denied" else "observed",
        "provider": _provider(payload, provider),
        "session": _session(payload.get("session_id")),
        "worktree": _worktree(cwd),
        "tool": "",
        "targets": [],
    }
    if kind == "compaction":
        source = payload.get("source") or ""
        if event not in {"PreCompact", "PostCompaction"} and not (
            event == "SessionStart" and source in {"compact", "resume"}
        ):
            return None
        path = payload.get("transcript_path") or ""
        result.update(
            tool="Compaction",
            counts=transcript_counts(path),
            trigger=payload.get("trigger") if payload.get("trigger") in {"manual", "auto"} else "",
            source=source if event == "SessionStart" else "",
        )
        return result
    tool = _label(payload.get("tool_name"), "")
    if kind == "tool" and not tool:
        return None
    values = payload.get("tool_input") or {}
    if not isinstance(values, dict):
        if kind == "tool" and tool == "Bash":
            return None
        values = {}
    if kind == "tool" and tool == "Bash" and not (values.get("command") or values.get("cmd")):
        return None
    result["tool"] = tool
    result["targets"] = _targets(tool, values, cwd)
    if (duration := _duration(payload)) is not None:
        result["duration_ms"] = duration
    return result


def transcript_counts(path: str) -> dict[str, int]:
    """Count transcript records and tool uses while keeping their bodies out of logs."""
    counts = {"messages": 0, "tool_uses": 0}
    if not isinstance(path, str) or not path:
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
    except OSError, TypeError:
        pass
    return counts


def _state_root(cwd: Path) -> Path | None:
    base_value = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    try:
        base = Path(base_value).expanduser()
        if not base.is_absolute():
            return None
        if _contains_symlink(base):
            return None
        base = base.resolve()
        if base == cwd or base.is_relative_to(cwd):
            return None
        return base / "agent-harness/audit"
    except OSError, RuntimeError, ValueError:
        return None


def _contains_symlink(path: Path) -> bool:
    """Reject a state path whose existing components could redirect an audit write."""
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if current.is_symlink():
            return True
    return False


def _files(root: Path) -> list[Path]:
    result: list[Path] = []
    try:
        worktrees = tuple(path for path in root.iterdir() if path.is_dir() and not path.is_symlink())
        providers = tuple(
            provider
            for worktree in worktrees
            for provider in worktree.iterdir()
            if provider.is_dir() and not provider.is_symlink()
        )
        for provider in providers:
            result.extend(path for path in provider.glob("*.jsonl") if not path.is_symlink() and path.is_file())
    except OSError:
        return result
    return result


def _cleanup(root: Path, now: float) -> None:
    stamp = root / ".cleanup"
    try:
        if stamp.exists() and now - stamp.stat().st_mtime < CLEANUP_INTERVAL_SECONDS:
            return
        if stamp.is_symlink():
            return
        descriptor = os.open(stamp, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        os.utime(stamp, (now, now))
        files = _files(root)
        for path in files:
            if now - path.stat().st_mtime > RETENTION_SECONDS:
                path.unlink(missing_ok=True)
        files = _files(root)
        total = sum(path.stat().st_size for path in files)
        for path in sorted(files, key=lambda item: item.stat().st_mtime_ns):
            if total <= TOTAL_LOG_LIMIT_BYTES:
                break
            total -= path.stat().st_size
            path.unlink(missing_ok=True)
    except OSError, ValueError:
        return


def prune(*, now: float | None = None) -> None:
    """Apply retention and total-size limits without affecting enforcement."""
    root = _state_root(Path.cwd().resolve())
    if root is None or not root.exists():
        return
    current = time.time() if now is None else now
    try:
        if _contains_symlink(root):
            return
        private_directory(root)
        with file_lock(root / ".lock"):
            _cleanup(root, current)
    except OSError, ValueError:
        return


def _append_path(directory: Path, session: str, now: datetime, size: int) -> Path | None:
    base = directory / f"{session}-{now:%Y%m%d}.jsonl"
    for sequence in range(10000):
        path = base if sequence == 0 else directory / f"{session}-{now:%Y%m%d}.{sequence}.jsonl"
        if path.is_symlink():
            continue
        try:
            if path.stat().st_size + size <= LOG_LIMIT_BYTES:
                return path
        except FileNotFoundError:
            return path
    return None


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if not written:
            raise OSError("audit log write made no progress")
        view = view[written:]


def append_record(entry: dict | None, *, cwd: Path | None = None) -> None:
    """Append one locked JSONL record; observation failures never block work."""
    if not isinstance(entry, dict):
        return
    current = datetime.now(UTC)
    root = _state_root(cwd.resolve() if cwd is not None else Path.cwd().resolve())
    if root is None or _contains_symlink(root):
        return
    record_value = dict(entry, ts=current.strftime("%Y-%m-%dT%H:%M:%SZ"))
    try:
        encoded = (json.dumps(record_value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        if len(encoded) > LOG_LIMIT_BYTES:
            return
        private_directory(root)
        with file_lock(root / ".lock"):
            provider = _label(record_value.get("provider"))
            session = _label(record_value.get("session"))
            worktree = record_value.get("worktree")
            if not isinstance(worktree, str) or not re.fullmatch(r"[0-9a-f]{32}", worktree):
                worktree = "unknown"
            record_value["worktree"] = worktree
            directory = root / worktree / provider
            if _contains_symlink(directory):
                return
            private_directory(directory)
            path = _append_path(directory, session, current, len(encoded))
            if path is None:
                return
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
            try:
                _write_all(descriptor, encoded)
            finally:
                os.close(descriptor)
            _cleanup(root, current.timestamp())
    except OSError, ValueError, TypeError:
        return


def blocked(
    tool: str,
    value: str = "",
    reason: str = "",
    hook: str = "",
    session: str = "",
    *,
    payload: dict | None = None,
    provider: str | None = None,
    targets: tuple[str, ...] = (),
) -> None:
    """Record a denial without using the supplied command or reason as log content."""
    context = dict(payload) if isinstance(payload, dict) else {}
    context.setdefault("tool_name", tool)
    context.setdefault("session_id", session)
    try:
        entry = record("denied", context, provider)
    except OSError, RuntimeError, TypeError, ValueError:
        return
    if entry is None:
        return
    entry["event"] = "Blocked"
    entry["status"] = "blocked"
    entry["rule"] = _label(hook)
    if targets:
        cwd = _cwd(context)
        entry["targets"] = [target for value in targets if (target := _target(value, cwd)) is not None][:MAX_TARGETS]
    append_record(entry, cwd=_cwd(context))


def main(arguments: list[str]) -> int:
    """Read an observational event without making logging an enforcement gate."""
    if len(arguments) not in {1, 2} or arguments[0] not in {"tool", "denied", "compaction"}:
        print("Usage: audit_log.py <tool|denied|compaction> [claude|codex|devin|hermes|pi]", file=sys.stderr)
        return 1
    if len(arguments) == 2 and arguments[1] not in {"claude", "codex", "devin", "hermes", "pi"}:
        print("Usage: audit_log.py <tool|denied|compaction> [claude|codex|devin|hermes|pi]", file=sys.stderr)
        return 1
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        entry = record(arguments[0], payload, arguments[1] if len(arguments) == 2 else None)
        append_record(entry, cwd=_cwd(payload))
    except ValueError, TypeError, AttributeError, OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
