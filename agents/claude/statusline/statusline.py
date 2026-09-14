#!/usr/bin/env -S python3 -IB
"""Render the two-line status display from structured provider input."""

import json
import math
import os
import subprocess
import sys
import time


SEPARATOR = "\033[38;5;240m │ \033[0m"


def segment(color: int, text: str) -> str:
    """Render a bold foreground segment."""
    return f"\033[1;38;5;{color}m{text}\033[0m"


def percentage(value: float) -> int:
    """Round used percentages like the provider's previous jq display."""
    return max(0, min(100, math.floor(value + 0.5)))


def bar(used: int, width: int = 4) -> str:
    """Show consumed capacity, using warmer colors as headroom shrinks."""
    units = percentage(used) * width * 8 // 100
    full, partial = divmod(units, 8)
    contents = "█" * full + " ▏▎▍▌▋▊▉"[partial].strip()
    contents += "░" * (width - full - bool(partial))
    color = 203 if used >= 80 else 220 if used >= 50 else 76
    return f"\033[38;5;{color}m{contents}\033[0m"


def duration(seconds: int) -> str:
    """Format elapsed time using the largest useful units."""
    days, remainder = divmod(max(0, seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def render(payload: dict, branch: str, now: int) -> str:
    """Format a provider snapshot without launching processes."""
    cwd = payload.get("cwd") or ""
    model = (payload.get("model") or {}).get("display_name") or ""
    first = [segment(14, os.path.basename(cwd.rstrip("/")) or cwd)]
    if branch:
        first.append(segment(10, branch))
    if model:
        first.append(segment(111, model))
    used = percentage((payload.get("context_window") or {}).get("used_percentage") or 0)
    second = [segment(252, "Ctx:") + bar(used) + segment(252, f" {used}%")]
    limits = payload.get("rate_limits") or {}
    for key, label, window, color in (("five_hour", "5h", 18000, 217), ("seven_day", "7d", 604800, 116)):
        limit = limits.get(key) or {}
        if limit.get("used_percentage") is None:
            continue
        used = percentage(limit["used_percentage"])
        remaining = int(limit.get("resets_at") or 0) - now
        prefix = f"{duration(max(0, window - remaining))}/" if remaining > 0 else ""
        second.append(segment(color, f"{prefix}{label}:") + bar(used) + segment(color, f" {used}%"))
    return SEPARATOR.join(first) + "\n" + SEPARATOR.join(second)


def main() -> int:
    """Read the snapshot and optionally obtain the current Git branch."""
    if sys.argv[1:]:
        print("Usage: statusline.py < hook-input.json", file=sys.stderr)
        return 0 if sys.argv[1:] in (["-h"], ["--help"]) else 1
    try:
        payload = json.load(sys.stdin)
        branch = ""
        if payload.get("cwd"):
            try:
                branch = subprocess.check_output(
                    ["git", "-C", payload["cwd"], "symbolic-ref", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
            except OSError, subprocess.CalledProcessError:
                pass
        print(render(payload, branch, int(time.time())))
    except ValueError, TypeError, AttributeError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
