"""Load command policy once and preserve the existing POSIX ERE matching contract."""

import json
import os
from pathlib import Path
import re
import subprocess


def regex_matches(pattern: str, value: str, insensitive: bool = False) -> bool:
    """Use the existing system regex engine instead of silently changing regex dialects."""
    flags = "-qiE" if insensitive else "-qE"
    result = subprocess.run(
        ["grep", flags, "-e", pattern],
        input=value + "\n",
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode > 1:
        raise ValueError("invalid POSIX extended regex rule")
    return result.returncode == 0


def load_rules(path: Path, prefixes: bool = False) -> list[dict]:
    """Validate policy at its boundary, including regex syntax before evaluating commands."""
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            raise ValueError("invalid version")
        rules = data.get("rules")
        if not isinstance(rules, list) or (not prefixes and not rules):
            raise ValueError("invalid rules")
        for rule in rules:
            if (
                not isinstance(rule, dict)
                or not isinstance(rule.get("justification"), str)
                or not rule["justification"]
            ):
                raise ValueError("missing justification")
            values = rule.get("prefix" if prefixes else "patterns")
            if (
                not isinstance(values, list)
                or not values
                or not all(isinstance(item, str) and item for item in values)
            ):
                raise ValueError("invalid command rule")
            if prefixes:
                if rule.get("decision") not in {"allow", "ask", "deny"}:
                    raise ValueError("invalid decision")
            else:
                for pattern in values:
                    regex_matches(pattern, "")
        return rules
    except (OSError, ValueError, TypeError) as error:
        raise ValueError(f"invalid command policy: {path}") from error


def project_file(name: str) -> Path | None:
    """Locate optional project policy using its owning Git root."""
    start = os.environ.get("AGENT_PROJECT_DIR", os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    try:
        root = subprocess.check_output(
            ["git", "-C", start, "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except OSError, subprocess.CalledProcessError:
        return None
    path = Path(root) / ".agents/hooks/rules" / name
    return path if path.is_file() else None


def prefix_reason(arguments: tuple[str, ...], rules: list[dict], decision: str) -> str:
    """Match complete parsed arguments rather than flattening away token boundaries."""
    return next(
        (
            rule["justification"]
            for rule in rules
            if rule["decision"] == decision and arguments[: len(rule["prefix"])] == tuple(rule["prefix"])
        ),
        "",
    )


def regex_reason(raw: str, rules: list[dict]) -> str:
    """Return the first applicable rule's stated rationale."""
    raw = re.sub(r"\s+(?:2>&1|2>/dev/null|>&2)\s*$", "", raw.strip())
    return next(
        (rule["justification"] for rule in rules if any(regex_matches(pattern, raw) for pattern in rule["patterns"])),
        "",
    )
