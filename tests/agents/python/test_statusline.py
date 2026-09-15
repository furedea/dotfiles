"""Statusline formatting can be checked without starting shells or Git."""

import re
import json
import os
from pathlib import Path
import subprocess

import pytest

from conftest import REPO_ROOT, load_script_module


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


def test_executable_entry_point_renders_the_two_line_snapshot(isolated_project: Path) -> None:
    script = REPO_ROOT / "agents/claude/statusline/statusline.py"
    assert script.is_file() and os.access(script, os.X_OK)
    result = subprocess.run(
        [str(script)],
        input=json.dumps(
            {
                "model": {"display_name": "Opus 4.6"},
                "cwd": str(isolated_project),
                "context_window": {"used_percentage": 25},
            }
        ),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert len(lines) == 2
    assert "Opus 4.6" in lines[0]
    assert "Ctx:" in lines[1] and "25%" in lines[1]
    assert "5h:" not in lines[1]


@pytest.mark.parametrize("percentage", [0, 100])
def test_context_endpoints_are_displayed(percentage: int) -> None:
    assert f"{percentage}%" in statusline.render({"context_window": {"used_percentage": percentage}}, "", 0)


def test_missing_model_does_not_drop_a_display_line() -> None:
    assert len(statusline.render({"model": {}, "context_window": {"used_percentage": 50}}, "", 0).splitlines()) == 2


def test_long_directory_is_reduced_to_the_current_name() -> None:
    first = statusline.render({"cwd": "/a/b/c/d/e"}, "", 0).splitlines()[0]
    assert "e" in first and "c/d/e" not in first


@pytest.mark.parametrize("window,label,percentage", [("five_hour", "5h:", 42), ("seven_day", "7d:", 15)])
def test_rate_limits_without_reset_time_still_show_usage(window: str, label: str, percentage: int) -> None:
    second = statusline.render(
        {"rate_limits": {window: {"used_percentage": percentage, "resets_at": None}}}, "", 0
    ).splitlines()[1]
    assert label in second and f"{percentage}%" in second
