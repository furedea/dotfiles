"""Validate scanner rules with the same PCRE2 engine used by the hook."""

import json
import shutil
import subprocess

import pytest

from tests.runtime import REPO_ROOT


PATTERNS = json.loads((REPO_ROOT / "agents/hooks/rules/secret_content_patterns.json").read_text())


def test_pattern_file_contains_rules() -> None:
    assert isinstance(PATTERNS, dict) and PATTERNS


@pytest.mark.parametrize("name", sorted(PATTERNS))
def test_pattern_has_nonempty_expression_and_message(name: str) -> None:
    rule = PATTERNS[name]
    assert isinstance(rule, dict)
    assert all(isinstance(rule.get(field), str) and rule[field] for field in ("pattern", "message"))


@pytest.mark.parametrize("name", sorted(PATTERNS))
def test_pattern_compiles_with_pcre2(name: str) -> None:
    ripgrep = shutil.which("rg")
    if ripgrep is None:
        pytest.skip("rg (ripgrep) is not available")
    result = subprocess.run(
        [ripgrep, "--pcre2", "-e", PATTERNS[name]["pattern"], "-"],
        input="\n",
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode in {0, 1}, result.stderr
