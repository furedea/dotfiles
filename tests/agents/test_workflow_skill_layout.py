"""Skill source contracts: metadata, link integrity, and handoff reachability.

These tests check rendering and link integrity, not claims about model compliance with prose.
"""

from collections import Counter
from collections.abc import Iterator
import json
from pathlib import Path
import re

import pytest

from tests.runtime import CliRunner, REPO_ROOT


SKILLS = REPO_ROOT / "agents/skills"
SKILL_NAMES = sorted(path.name for path in SKILLS.iterdir() if path.is_dir())
SKILL_RENDERING = REPO_ROOT / "agents/skill_rendering.json"
FENCED_CODE_PATTERN = re.compile(r"^(```|~~~).*?^\1\s*$", re.MULTILINE | re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]*`")
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\)")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
FRONTMATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
FRONTMATTER_KEY_PATTERN = re.compile(r"^([A-Za-z][\w-]*):[ \t]*(.*)$")
SKILL_HANDOFF_PATTERN = re.compile(r"^\.\./([^/]+)/SKILL\.md$")


@pytest.mark.integration
@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_issue_skill_renders_with_implicit_invocation(agent_harness: CliRunner, tmp_path: Path, provider: str) -> None:
    output = tmp_path / provider
    # The production renderer parses and validates source frontmatter.
    agent_harness("generate-skills", "--provider", provider, "--output", str(output))
    rendered = output / "issue-workflow/SKILL.md"
    text = rendered.read_text()
    frontmatter = text.split("---", 2)[1]
    assert re.search(r"^name:\s*issue-workflow\s*$", frontmatter, re.MULTILINE)
    assert re.search(r"^description:\s*\S", frontmatter, re.MULTILINE)
    assert not re.search(r"^disable-model-invocation:\s*true\s*$", frontmatter, re.MULTILINE)
    metadata = output / "issue-workflow/agents/openai.yaml"
    if metadata.exists():
        assert not re.search(r"allow_implicit_invocation:\s*false", metadata.read_text())
    assert not _is_model_invocation_disabled("issue-workflow")


@pytest.mark.integration
@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_every_skill_renders_with_its_name_and_description(
    agent_harness: CliRunner, tmp_path: Path, provider: str
) -> None:
    output = tmp_path / provider
    agent_harness("generate-skills", "--provider", provider, "--output", str(output))
    for skill in SKILL_NAMES:
        frontmatter = _frontmatter((output / skill / "SKILL.md").read_text())
        assert frontmatter.get("name") == skill, skill
        assert frontmatter.get("description"), skill


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_skill_frontmatter_names_its_directory_and_describes_it(skill: str) -> None:
    frontmatter = _frontmatter((SKILLS / skill / "SKILL.md").read_text())

    assert frontmatter.get("name") == skill
    assert frontmatter.get("description")


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_skill_relative_links_resolve_to_existing_files_and_headings(skill: str) -> None:
    broken_links = [
        (str(path.relative_to(SKILLS)), destination)
        for path, destination in _relative_links(SKILLS / skill)
        if not _link_resolves(path, destination)
    ]

    assert broken_links == []


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_skill_handoff_links_name_existing_skills(skill: str) -> None:
    missing_skills = sorted(target for target in _linked_skills(SKILLS / skill) if target not in SKILL_NAMES)

    assert missing_skills == []


@pytest.mark.parametrize("skill", SKILL_NAMES)
def test_skill_handoff_targets_allow_model_invocation(skill: str) -> None:
    disabled_targets = sorted(
        target
        for target in _handoff_targets(SKILLS / skill)
        if target != skill and _is_model_invocation_disabled(target)
    )

    assert disabled_targets == []


def _frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_PATTERN.match(text)
    assert match is not None, "SKILL.md must start with YAML frontmatter"
    fields: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in match.group(1).splitlines():
        key_match = FRONTMATTER_KEY_PATTERN.match(line)
        if key_match is not None:
            current_key = key_match.group(1)
            fields[current_key] = [key_match.group(2)]
        elif current_key is not None and line[:1].isspace():
            fields[current_key].append(line)
    return {key: _scalar(parts) for key, parts in fields.items()}


def _scalar(parts: list[str]) -> str:
    head, *continuation = parts
    words = continuation if head.strip() in {">", "|", ">-", "|-"} else [head, *continuation]
    return " ".join(word.strip() for word in words).strip().strip("\"'")


def _relative_links(skill_directory: Path) -> Iterator[tuple[Path, str]]:
    for path in sorted(skill_directory.rglob("*.md")):
        for destination in LINK_PATTERN.findall(_prose(path.read_text())):
            if not re.match(r"^[a-z][a-z0-9+.-]*:", destination, re.IGNORECASE):
                yield path, destination


def _link_resolves(source: Path, destination: str) -> bool:
    filename, _, anchor = destination.partition("#")
    target = (source.parent / filename).resolve() if filename else source
    if not target.is_file():
        return False
    return not anchor or target.suffix != ".md" or anchor in _heading_anchors(target)


def _heading_anchors(path: Path) -> set[str]:
    counts: Counter[str] = Counter()
    anchors: set[str] = set()
    for heading in HEADING_PATTERN.findall(_prose(path.read_text(), keep_inline_code=True)):
        slug = _github_slug(heading)
        anchors.add(f"{slug}-{counts[slug]}" if counts[slug] else slug)
        counts[slug] += 1
    return anchors


def _github_slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def _handoff_targets(skill_directory: Path) -> set[str]:
    return _linked_skills(skill_directory) | _skills_named_in_inline_code(skill_directory)


def _linked_skills(skill_directory: Path) -> set[str]:
    return {
        match.group(1)
        for _, destination in _relative_links(skill_directory)
        if (match := SKILL_HANDOFF_PATTERN.match(destination.partition("#")[0])) is not None
    }


def _skills_named_in_inline_code(skill_directory: Path) -> set[str]:
    return {
        code.strip("`")
        for path in skill_directory.rglob("*.md")
        for code in INLINE_CODE_PATTERN.findall(_prose(path.read_text(), keep_inline_code=True))
        if code.strip("`") in SKILL_NAMES
    }


def _is_model_invocation_disabled(skill: str) -> bool:
    settings = json.loads(SKILL_RENDERING.read_text())["skills"].get(skill, {})
    claude_disabled = settings.get("claude", {}).get("frontmatter", {}).get("disable-model-invocation") is True
    codex_disabled = settings.get("codex", {}).get("openai", {}).get("allow_implicit_invocation") is False
    return claude_disabled or codex_disabled


def _prose(text: str, *, keep_inline_code: bool = False) -> str:
    without_fences = FENCED_CODE_PATTERN.sub("", text)
    return without_fences if keep_inline_code else INLINE_CODE_PATTERN.sub("", without_fences)
