"""Rendering and link integrity, not claims about model compliance with prose."""

import json
from pathlib import Path
import re

import pytest

from tests.runtime import CliRunner, REPO_ROOT


SKILLS = REPO_ROOT / "agents/skills"
WORKFLOW_SKILLS = ("issue-workflow", "git-workflow", "source-of-truth", "tsdd")


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
    config = json.loads((REPO_ROOT / "agents/skill_rendering.json").read_text())
    settings = config["skills"].get("issue-workflow", {})
    assert settings.get("claude", {}).get("frontmatter", {}).get("disable-model-invocation") is not True
    assert settings.get("codex", {}).get("openai", {}).get("allow_implicit_invocation") is not False


def test_workflow_local_links_resolve_and_retired_issue_reference_is_absent() -> None:
    assert not (SKILLS / "git-workflow/references/issues.md").exists()
    for name in WORKFLOW_SKILLS:
        for path in (SKILLS / name).rglob("*.md"):
            text = path.read_text()
            for destination in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                filename = destination.split("#", 1)[0]
                if not filename or "://" in filename:
                    continue
                assert (path.parent / filename).is_file(), (path, destination)
                assert not filename.endswith("/issues.md"), (path, destination)


CHANGED_SKILLS = ("herdr-delegation", "tsdd", "github-actions-style")


@pytest.mark.integration
@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("skill", CHANGED_SKILLS)
def test_changed_skills_render_with_valid_frontmatter(
    agent_harness: CliRunner, tmp_path: Path, provider: str, skill: str
) -> None:
    output = tmp_path / provider
    agent_harness("generate-skills", "--provider", provider, "--output", str(output))
    text = (output / skill / "SKILL.md").read_text()
    frontmatter = text.split("---", 2)[1]
    assert re.search(rf"^name:\s*{re.escape(skill)}\s*$", frontmatter, re.MULTILINE)
    assert re.search(r"^description:\s*\S", frontmatter, re.MULTILINE)


@pytest.mark.parametrize("skill", CHANGED_SKILLS)
def test_changed_skill_links_resolve(skill: str) -> None:
    for path in (SKILLS / skill).rglob("*.md"):
        for destination in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
            filename = destination.split("#", 1)[0]
            if not filename or "://" in filename:
                continue
            assert (path.parent / filename).is_file(), (path, destination)


@pytest.mark.integration
def test_generated_github_actions_skill_drops_only_the_blacksmith_section(
    agent_harness: CliRunner, tmp_path: Path
) -> None:
    output = tmp_path / "claude"
    agent_harness("generate-skills", "--provider", "claude", "--output", str(output))
    rendered = (output / "github-actions-style/SKILL.md").read_text()
    assert "blacksmith" not in rendered.lower()
    assert "blacksmith" not in (SKILLS / "github-actions-style/SKILL.md").read_text().lower()
    assert "## 7. Cache Design" in rendered


def test_no_review_or_ponytail_skill_was_added() -> None:
    names = {path.name for path in SKILLS.iterdir() if path.is_dir()}
    assert not any("review" in name or "ponytail" in name for name in names)
