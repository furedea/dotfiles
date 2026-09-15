"""Check secretary documentation contracts, not runtime permission enforcement."""

import re

import pytest

from tests.runtime import REPO_ROOT


SKILL_DIRECTORY = REPO_ROOT / "hermes/secretary/skills/secretary"


@pytest.mark.parametrize(
    "name",
    [
        "apple-mail",
        "calendar-briefing",
        "google-calendar",
        "mail-triage",
        "morning-briefing",
        "research-digest",
        "tech-digest",
    ],
)
def test_secretary_exposes_each_focused_skill(name: str) -> None:
    source = (SKILL_DIRECTORY / name / "SKILL.md").read_text()
    assert f"name: {name}" in source
    assert "## When to Use" in source


def test_morning_blueprint_limits_writes_to_local_digest_state() -> None:
    source = (SKILL_DIRECTORY / "morning-briefing/SKILL.md").read_text()
    for contract in (
        "blueprint:",
        'schedule: "0 8 * * *"',
        "prompt: Prepare today",
        "Keep providers read-only; only local digest state may change.",
        "enabled_toolsets: [terminal, skills]",
    ):
        assert contract in source


def test_morning_routine_requests_a_japanese_report() -> None:
    source = (SKILL_DIRECTORY / "morning-briefing/SKILL.md").read_text()
    assert re.search(r"^5\. Produce one concise .*Japanese report", source, re.MULTILINE)
