"""Validate staged-filename policy with its actual POSIX ERE engine."""

import json
import subprocess

import pytest

from conftest import REPO_ROOT


POLICY = json.loads((REPO_ROOT / "agents/hooks/rules/secret_commit_policy.json").read_text())


def test_commit_policy_has_the_supported_schema() -> None:
    assert isinstance(POLICY, dict)
    assert type(POLICY.get("version")) is int and POLICY["version"] == 1
    assert isinstance(POLICY.get("rules"), list) and POLICY["rules"]
    for rule in POLICY["rules"]:
        assert isinstance(rule, dict)
        assert all(isinstance(rule.get(field), str) and rule[field] for field in ("pattern", "reason"))


@pytest.mark.parametrize("rule", POLICY["rules"], ids=lambda rule: rule["reason"])
def test_filename_pattern_compiles_as_posix_ere(rule: dict[str, str]) -> None:
    result = subprocess.run(
        ["grep", "-E", "-e", rule["pattern"]],
        input="",
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode in {0, 1}, result.stderr
