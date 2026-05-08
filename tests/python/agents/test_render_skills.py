import pytest

from tests.python.conftest import load_script_module


render_skills = load_script_module("agents/scripts/render_skills.py", "render_skills")


def test_render_skill_appends_provider_overrides_in_sorted_order() -> None:
    rendered = render_skills.render_skill(
        ["name: example", "description: Common description."],
        {
            "disable-model-invocation": True,
            "allowed-tools": ["Bash", "Read"],
            "argument-hint": "{mode}",
        },
        "# Body\n",
    )

    assert rendered == (
        "---\n"
        "name: example\n"
        "description: Common description.\n"
        'allowed-tools: ["Bash", "Read"]\n'
        'argument-hint: "{mode}"\n'
        "disable-model-invocation: true\n"
        "---\n"
        "# Body\n"
    )


def test_common_frontmatter_entries_rejects_provider_specific_keys() -> None:
    frontmatter = 'name: example\ndescription: Common.\nallowed-tools: ["Bash"]\n'

    with pytest.raises(ValueError, match="non-common frontmatter keys"):
        render_skills.common_frontmatter_entries("agents/skills/example/SKILL.md", frontmatter)


def test_split_frontmatter_requires_yaml_markers() -> None:
    with pytest.raises(ValueError, match="must start with YAML frontmatter"):
        render_skills.split_frontmatter("name: example\n")
