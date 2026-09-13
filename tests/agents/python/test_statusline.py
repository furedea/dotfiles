"""Statusline formatting can be checked without starting shells or Git."""

import re

import pytest

from conftest import load_script_module


statusline = load_script_module("agents/claude/statusline/statusline.py", "statusline")


@pytest.mark.parametrize(("seconds", "expected"), [(90061, "1d 1h"), (7260, "2h 1m"), (300, "5m"), (0, "0m")])
def test_duration_uses_largest_useful_units(seconds: int, expected: str) -> None:
    assert statusline.duration(seconds) == expected


@pytest.mark.parametrize(("percentage", "expected"), [(0, "░░░░"), (25, "█░░░"), (100, "████")])
def test_bar_represents_consumed_capacity(percentage: int, expected: str) -> None:
    assert re.sub(r"\x1b\[[0-9;]*m", "", statusline.bar(percentage)) == expected


def test_rate_window_displays_elapsed_time() -> None:
    rendered = statusline.render({"rate_limits": {"five_hour": {"used_percentage": 42, "resets_at": 18000}}}, "", 3600)
    assert "1h 0m/5h:" in rendered
    assert "42%" in rendered


def test_expired_rate_window_has_no_misleading_elapsed_prefix() -> None:
    rendered = statusline.render({"rate_limits": {"five_hour": {"used_percentage": 42, "resets_at": 100}}}, "", 101)
    assert "5h:" in rendered
    assert "/5h" not in rendered
