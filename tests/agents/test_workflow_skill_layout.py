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
