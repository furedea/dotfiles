#!/usr/bin/env -S python3 -IB
"""Hand any new lint or type-check suppression in code to the user.

The numeric AGENTS.md rules are enforced by lint, and a real exception gets a per-site suppression
with a reason. Whether an exception is real is the user's judgment, so an edit that adds more
suppression markers to a code file than it removes asks; moving or deleting one does not.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import audit_log
import hook_decision
import hook_input
from hook_decision import Verdict


RULE = "guard_suppression.sh"
CODE_SUFFIXES = frozenset(
    {".py", ".pyi", ".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs", ".rs", ".sh", ".bash", ".lua"}
)
MARKERS = {
    "noqa": re.compile(r"#\s*(?:ruff:\s*)?noqa\b"),
    "type: ignore": re.compile(r"#\s*type:\s*ignore\b"),
    "pyright: ignore": re.compile(r"#\s*pyright:\s*ignore\b"),
    "pylint: disable": re.compile(r"#\s*pylint:\s*disable\b"),
    "lint-disable comment": re.compile(r"\b(?:oxlint|eslint)-disable\b"),
    "biome-ignore": re.compile(r"\bbiome-ignore\b"),
    "@ts-ignore": re.compile(r"@ts-(?:ignore|expect-error|nocheck)\b"),
    "allow or expect attribute": re.compile(r"#!?\[\s*(?:allow|expect)\s*\("),
    "shellcheck disable": re.compile(r"#\s*shellcheck\s+disable="),
}
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$")


@dataclass(frozen=True, slots=True)
class Change:
    path: str
    added: str
    removed: str


def decide(payload: dict) -> Verdict:
    added = [(change.path, name) for change in changes(payload) for name in new_markers(change)]
    if not added:
        return hook_decision.ALLOW
    listed = ", ".join(f"{name} in {path}" for path, name in added)
    return hook_decision.ask(
        f"Needs review: this edit adds a lint or type-check suppression ({listed}). "
        "Only the user decides whether an exception is warranted; state the reason.",
        "suppression",
    )


def new_markers(change: Change) -> list[str]:
    if Path(change.path).suffix not in CODE_SUFFIXES:
        return []
    found = []
    for name, pattern in MARKERS.items():
        if len(pattern.findall(change.added)) > len(pattern.findall(change.removed)):
            found.append(name)
    return found


def changes(payload: dict) -> list[Change]:
    tool = payload.get("tool_name") or ""
    values = payload.get("tool_input") or {}
    if tool == "apply_patch" or "patch" in values:
        return patch_changes(hook_input.patch_body(values, tool or None))
    path = hook_input.file_path(values)
    if tool == "Write":
        return [Change(path, values.get("content") or "", existing_text(path))]
    if tool == "MultiEdit":
        edits = values.get("edits") or []
        return [
            Change(
                path,
                "".join(e.get("new_string") or "" for e in edits),
                "".join(e.get("old_string") or "" for e in edits),
            )
        ]
    return [Change(path, values.get("new_string") or "", values.get("old_string") or "")]


def patch_changes(patch: str) -> list[Change]:
    """Split an apply_patch body into per-file added and removed text."""
    added: dict[str, list[str]] = {}
    removed: dict[str, list[str]] = {}
    current = ""
    for line in patch.splitlines():
        if match := PATCH_FILE.match(line):
            current = match.group(1).strip()
            added.setdefault(current, [])
            removed.setdefault(current, [])
        elif current and line.startswith("+"):
            added[current].append(line[1:])
        elif current and line.startswith("-"):
            removed[current].append(line[1:])
    return [Change(path, "\n".join(added[path]), "\n".join(removed[path])) for path in added]


def existing_text(path: str) -> str:
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError, OSError:
        print("BLOCKED: failed to parse tool input JSON", file=sys.stderr)
        return 2
    verdict = decide(payload)
    if verdict.decision != "allow":
        audit_log.escalated(
            audit_log.Refusal(
                payload.get("tool_name") or "Edit",
                RULE,
                payload.get("session_id", ""),
                payload=payload,
                detail=verdict.detail,
            )
        )
    return hook_decision.emit(verdict)


if __name__ == "__main__":
    sys.exit(main())
