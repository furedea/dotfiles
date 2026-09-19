"""Decode apply_patch headers and inserted text without executing the patch."""

import re


def is_patch(text: str) -> bool:
    """Recognize patch format independently of which input field carried it."""
    return bool(
        re.search(r"^\*\*\* (?:Begin Patch|End Patch|(?:Add|Update|Delete) File:|Move to:)", text, re.MULTILINE)
    )


def paths(patch: str) -> tuple[str, ...]:
    return tuple(
        sorted(set(re.findall(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$", patch, re.MULTILINE)))
    )


def added_text(patch: str) -> str:
    return "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
