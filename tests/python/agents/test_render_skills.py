import pathlib

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


def test_write_extra_files_creates_nested_directories(tmp_path: pathlib.Path) -> None:
    provider_dir = tmp_path / "skill"
    provider_dir.mkdir()
    content = "policy:\n  allow_implicit_invocation: false\n"

    render_skills.write_extra_files(provider_dir, {"agents/openai.yaml": content})

    written = provider_dir / "agents" / "openai.yaml"
    assert written.read_text() == content


def test_write_extra_files_rejects_path_escape(tmp_path: pathlib.Path) -> None:
    provider_dir = tmp_path / "skill"
    provider_dir.mkdir()

    with pytest.raises(ValueError, match="must be relative"):
        render_skills.write_extra_files(provider_dir, {"../escape.yaml": "x"})


def test_write_extra_files_rejects_absolute_path(tmp_path: pathlib.Path) -> None:
    provider_dir = tmp_path / "skill"
    provider_dir.mkdir()

    with pytest.raises(ValueError, match="must be relative"):
        render_skills.write_extra_files(provider_dir, {"/etc/passwd": "x"})


def test_render_all_grants_write_when_source_is_readonly(tmp_path: pathlib.Path) -> None:
    source_dir = tmp_path / "skills"
    skill_dir = source_dir / "demo"
    sibling_dir = skill_dir / "agents"
    sibling_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill.\n---\n# Demo\n",
    )
    sibling = sibling_dir / "helper.md"
    sibling.write_text("helper")
    sibling.chmod(0o444)
    sibling_dir.chmod(0o555)

    output_dir = tmp_path / "out"
    overrides = {
        "demo": {
            "files": {"codex": {"agents/openai.yaml": "policy: {}\n"}},
        },
    }

    try:
        render_skills.render_all(source_dir, output_dir, overrides)

        emitted = output_dir / "codex" / "skills" / "demo" / "agents" / "openai.yaml"
        assert emitted.read_text() == "policy: {}\n"
    finally:
        sibling_dir.chmod(0o755)
        sibling.chmod(0o644)


def test_render_all_emits_codex_sibling_files(tmp_path: pathlib.Path) -> None:
    source_dir = tmp_path / "skills"
    skill_dir = source_dir / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill.\n---\n# Demo\n",
    )
    output_dir = tmp_path / "out"

    overrides = {
        "demo": {
            "frontmatter": {
                "claude": {"disable-model-invocation": True},
            },
            "files": {
                "codex": {"agents/openai.yaml": "policy:\n  allow_implicit_invocation: false\n"},
            },
        },
    }

    render_skills.render_all(source_dir, output_dir, overrides)

    claude_skill = (output_dir / "claude" / "skills" / "demo" / "SKILL.md").read_text()
    assert "disable-model-invocation: true" in claude_skill

    codex_policy = output_dir / "codex" / "skills" / "demo" / "agents" / "openai.yaml"
    assert codex_policy.read_text() == "policy:\n  allow_implicit_invocation: false\n"

    claude_policy = output_dir / "claude" / "skills" / "demo" / "agents" / "openai.yaml"
    assert not claude_policy.exists()
