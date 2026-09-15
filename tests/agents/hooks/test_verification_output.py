"""Runner output is evidence only for observations it actually reports."""

import pytest

from tests.runtime import load_script_module


output = load_script_module("agents/hooks/lib/verification_output.py", "verification_output")


@pytest.mark.parametrize(
    ("label", "text", "executed"),
    [
        ("bats", "1..1\nok 1 skipped # skip unavailable service", 0),
        ("bats", "1..2\nok 1 first\nnot ok 2 second", 2),
        ("bats", "1..0", 0),
        ("pytest", "2 passed, 3 skipped in 0.1s", 2),
        ("pytest", "3 skipped in 0.1s", 0),
        ("rust", "test result: ok. 2 passed; 0 failed;\ntest result: ok. 0 passed; 0 failed;", 2),
        ("rust", "test result: ok. 0 passed; 0 failed; 12 filtered out;", 0),
        ("vitest", "No test files found", 0),
        ("vitest", "Tests  3 passed (3)", 3),
        ("node", "# pass 2\n# fail 1", 3),
        ("pytest", "unrecognized runner output", None),
    ],
)
def test_executed_count_distinguishes_absence_from_unknown(label: str, text: str, executed: int | None) -> None:
    assert output.summarize(label, text).executed == executed


def test_partial_bats_plan_is_visible() -> None:
    assert output.summarize("bats", "1..3\nok 1 first").summary == "1 passed (partial results; 3 planned)"


def test_bats_summary_preserves_skipped_tests() -> None:
    assert output.summarize("bats", "1..3\nok 1 a\nok 2 b\nok 3 c # SKIP offline").summary == "2 passed, 1 skipped"


def test_diagnostic_prefers_actual_failure_over_runner_banner() -> None:
    assert output.first_error("starting runner\nFAILED test_example\nmore details") == "FAILED test_example"
