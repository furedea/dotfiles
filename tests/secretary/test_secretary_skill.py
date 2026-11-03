"""Check secretary documentation and settings contracts, not runtime permission enforcement."""

import json
import re

import pytest

from tests.runtime import REPO_ROOT


SECRETARY_DIRECTORY = REPO_ROOT / "secretary"
SKILL_DIRECTORY = SECRETARY_DIRECTORY / ".claude/skills"
SKILL_NAMES = [
    "ai-research-digest",
    "apple-mail",
    "calendar-briefing",
    "mail-triage",
    "morning-briefing",
    "toolchain-digest",
]
DIGEST_STATE_FILES = {
    "ai-research-digest": "~/.local/state/secretary/research-digest.json",
    "toolchain-digest": "~/.local/state/secretary/tech-digest.json",
}


def load_settings(name: str) -> dict:
    return json.loads((SECRETARY_DIRECTORY / name).read_text())["permissions"]


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_secretary_exposes_each_focused_skill(name: str) -> None:
    source = (SKILL_DIRECTORY / name / "SKILL.md").read_text()
    assert f"name: {name}" in source
    assert "## When to Use" in source


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_skills_do_not_reference_hermes(name: str) -> None:
    source = (SKILL_DIRECTORY / name / "SKILL.md").read_text().lower()
    for stale in ("hermes", "metadata:", "blueprint", "~/.hermes", "write_file"):
        assert stale not in source


@pytest.mark.parametrize(("name", "state_path"), DIGEST_STATE_FILES.items())
def test_digest_skills_keep_state_under_local_state(name: str, state_path: str) -> None:
    source = (SKILL_DIRECTORY / name / "SKILL.md").read_text()
    assert state_path in source


def test_morning_routine_requests_a_japanese_report() -> None:
    source = (SKILL_DIRECTORY / "morning-briefing/SKILL.md").read_text()
    assert re.search(r"^5\. Produce one concise .*Japanese report", source, re.MULTILINE)


def test_morning_routine_keeps_every_report_section() -> None:
    source = (SKILL_DIRECTORY / "morning-briefing/SKILL.md").read_text()
    for section in (
        "attention now",
        "today's schedule",
        "mail requiring a decision",
        "AI4SE research",
        "LLM and agent benchmark research",
        "material technology changes",
        "coverage gaps",
    ):
        assert f"- {section}" in source


def test_briefing_settings_deny_provider_mutations() -> None:
    permissions = load_settings(".claude/settings.json")
    deny = set(permissions["deny"])
    assert {
        "Bash(apple-mail mark-read *)",
        "Bash(apple-mail move *)",
        "Bash(apple-mail get *--include-body*)",
        "Edit(~/ghq/**)",
    } <= deny
    assert "Edit" not in deny
    assert permissions["defaultMode"] == "dontAsk"


def test_briefing_settings_allow_only_digest_state_writes() -> None:
    allow = load_settings(".claude/settings.json")["allow"]
    assert not [rule for rule in allow if rule.startswith("Write(")]
    writes = [rule for rule in allow if rule.startswith("Edit(")]
    assert sorted(writes) == [
        "Edit(~/.local/state/secretary/research-digest.json.tmp)",
        "Edit(~/.local/state/secretary/tech-digest.json.tmp)",
    ]
    moves = [rule for rule in allow if rule.startswith("Bash(mv ")]
    assert len(moves) == 2
    assert all("~/.local/state/secretary/" in rule for rule in moves)


def test_briefing_settings_never_allow_mail_mutation() -> None:
    allow = load_settings(".claude/settings.json")["allow"]
    assert not [rule for rule in allow if "mark-read" in rule or "apple-mail move" in rule]
    assert "Bash(apple-mail get *)" in allow


def test_briefing_settings_cannot_send_mail_or_run_osascript() -> None:
    permissions = load_settings(".claude/settings.json")
    assert "Bash(osascript *)" in permissions["deny"]
    assert not [rule for rule in permissions["allow"] if "osascript" in rule]
    assert not (SECRETARY_DIRECTORY / "publish.settings.json").exists()


def test_mail_triage_excludes_the_briefing_self_mail() -> None:
    source = (SKILL_DIRECTORY / "mail-triage/SKILL.md").read_text()
    assert "`[briefing]`" in source
    assert "Exclude self-addressed mail" in source


def test_briefing_settings_use_read_only_web_tools_instead_of_curl() -> None:
    permissions = load_settings(".claude/settings.json")
    assert not [rule for rule in permissions["allow"] if "curl" in rule or "wget" in rule]
    assert {"WebFetch", "WebSearch"} <= set(permissions["allow"])
    assert {"Bash(curl *)", "Bash(wget *)"} <= set(permissions["deny"])


def test_briefing_settings_read_calendar_json_and_drop_gws() -> None:
    permissions = load_settings(".claude/settings.json")
    assert "Read(~/.local/state/secretary/**)" in permissions["allow"]
    assert not [rule for rule in permissions["allow"] if "gws" in rule]
    assert not (SKILL_DIRECTORY / "google-calendar").exists()


def test_calendar_briefing_reads_the_exported_json_only() -> None:
    source = (SKILL_DIRECTORY / "calendar-briefing/SKILL.md").read_text()
    assert "~/.local/state/secretary/calendar/" in source
    assert "gws" not in source
    assert "google-calendar" not in source


def test_morning_briefing_emits_the_coverage_marker_first() -> None:
    source = (SKILL_DIRECTORY / "morning-briefing/SKILL.md").read_text()
    assert "coverage: complete" in source
    assert "coverage: partial" in source
