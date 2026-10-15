"""Carry one guard's verdict to whichever provider asked, in the Claude-native hook contract."""

from dataclasses import dataclass, replace
import json
import sys
from typing import Literal, Self


Decision = Literal["allow", "ask", "deny"]
REVIEW_HINT = "Use a non-destructive approved form, or ask the user to review the command policy."


@dataclass(frozen=True, slots=True)
class Verdict:
    """Allow silently, ask the user, or deny with a reason the model can act on.

    `detail` is a short audit label such as the governed prefix, never command text.
    """

    decision: Decision
    reason: str = ""
    detail: str = ""

    def hardened(self) -> Self:
        """Turn a prompt into a denial for providers whose hooks cannot ask the user."""
        return replace(self, decision="deny") if self.decision == "ask" else self


ALLOW = Verdict("allow")


def ask(reason: str, detail: str = "") -> Verdict:
    return Verdict("ask", reason, detail)


def deny(reason: str, detail: str = "") -> Verdict:
    return Verdict("deny", reason, detail)


def emit(verdict: Verdict) -> int:
    """Report the verdict as a native Claude PreToolUse hook does and return the hook exit status."""
    if verdict.decision == "deny":
        print(verdict.reason, file=sys.stderr)
        return 2
    if verdict.decision == "ask":
        print(json.dumps(escalation(verdict.reason), ensure_ascii=True, separators=(",", ":")))
    return 0


def escalation(reason: str) -> dict:
    """Shape an ask decision as Claude Code reads it; adapters translate it for other providers."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }
