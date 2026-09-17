"""Load command policy once and preserve the existing POSIX ERE matching contract."""

from collections.abc import Sequence
import json
import os
from pathlib import Path
import re
import subprocess

import git_safety
import shell_syntax


def regex_matches(pattern: str, value: str, insensitive: bool = False) -> bool:
    """Use the existing system regex engine instead of silently changing regex dialects."""
    return any_regex_matches((pattern,), value, insensitive)


def any_regex_matches(patterns: Sequence[str], value: str, insensitive: bool = False) -> bool:
    """Spawn one grep for a whole pattern set; process start-up, not matching, dominates each decision."""
    if not patterns:
        return False
    flags = "-qiE" if insensitive else "-qE"
    selectors = [argument for pattern in patterns for argument in ("-e", pattern)]
    result = subprocess.run(
        ["grep", flags, *selectors],
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
            if prefixes and rule.get("decision") not in {"allow", "ask", "deny"}:
                raise ValueError("invalid decision")
        if not prefixes:
            any_regex_matches(all_patterns(rules), "")
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


def canonical(command: shell_syntax.Command) -> shell_syntax.Command:
    """Judge a program by its name and Git by its subcommand, not by install path or global options."""
    name = Path(command.arguments[0]).name
    if name != "git":
        return command.rebased(1, (name,))
    globals_, _ = git_safety.git_arguments(command.arguments)
    return command.rebased(1 + len(globals_), ("git",))


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
    """Return the first applicable rule's stated rationale, asking grep once before locating that rule."""
    raw = re.sub(r"\s+(?:2>&1|2>/dev/null|>&2)\s*$", "", raw.strip())
    if not any_regex_matches(all_patterns(rules), raw):
        return ""
    return next((rule["justification"] for rule in rules if any_regex_matches(rule["patterns"], raw)), "")


def all_patterns(rules: list[dict]) -> list[str]:
    return [pattern for rule in rules for pattern in rule["patterns"]]
