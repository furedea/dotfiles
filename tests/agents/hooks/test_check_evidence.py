"""Runner output is evidence only for observations it actually reports."""

import pytest

from tests.runtime import load_script_module


output = load_script_module("agents/hooks/lib/check_evidence.py", "check_evidence")


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


@pytest.mark.parametrize("runner", ["vitest", "jest", "node", "npm test", "pnpm test", "yarn test", "bun test"])
def test_javascript_runner_summaries_follow_rust_and_precede_bats(runner: str) -> None:
    lines = [
        "Bats: 50 passed · 11 targets · 33.8s",
        f"{runner}: 3 passed · full suite · 0.5s",
        "rust: 2 passed · full suite · 0.3s",
        "pytest: 989 passed · 38 files · 140.0s",
    ]
    assert output.ordered_lines(lines) == [lines[3], lines[2], lines[1], lines[0]]
    assert lines[0].startswith("Bats:")


def test_display_order_preserves_multiple_results_and_configuration_errors() -> None:
    lines = [
        "configuration: unavailable · project test rules",
        "Bats: 1 passed · 1 targets · 0.1s",
        "rust: 2 passed · unit filter first · 0.2s",
        "pytest: 3 passed · 1 files · 0.3s",
        "rust: 4 passed · integration target second · 0.4s",
    ]
    assert output.ordered_lines(lines) == [lines[0], lines[3], lines[2], lines[4], lines[1]]
