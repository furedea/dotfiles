"""Match the shared secret-path policy against parsed literal path candidates."""

from fnmatch import fnmatchcase
import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            raise ValueError("unsupported policy version")
        rules = data.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValueError("empty rules")
        if not all(
            isinstance(rule, dict)
            and all(isinstance(rule.get(key), str) and rule[key] for key in ("pattern", "reason"))
            for rule in rules
        ):
            raise ValueError("invalid path rule")
        return rules
    except (OSError, ValueError) as error:
        raise ValueError(f"secret path policy was not found or is invalid: {path}") from error


def normalize(value: str) -> str:
    if value.startswith("$HOME/"):
        return "~/" + value[6:]
    home = str(Path.home()) + "/"
    return "~/" + value[len(home) :] if value.startswith(home) else value


def candidate(value: str) -> bool:
    return "/" in value or "." in value or value in {"id_rsa", "id_ed25519"}


def blocked_rule(value: str, rules: list[dict]) -> dict | None:
    if not candidate(value):
        return None
    path = normalize(value)
    # Do not resolve symlinks: this policy concerns named paths, not a sandbox.
    for rule in rules:
        pattern = rule["pattern"]
        if fnmatchcase(path, pattern) or (pattern.startswith("**/") and fnmatchcase(path, pattern[3:])):
            return rule
    return None
