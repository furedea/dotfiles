from pathlib import Path
import json
from pytest_mock import MockerFixture

from tests.agents.python.conftest import load_script_module


collect_skills = load_script_module(
    "agents/skills/skill-auditor/scripts/collect_skills.py",
    "skill_auditor_collect_skills",
)


def write_skill(path: Path, name: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use when testing {name}.\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_codex_default_skill_dirs_include_stable_codex_locations() -> None:
    dirs = collect_skills.default_skill_dirs("codex")

    assert "~/.codex/skills" in dirs
    assert "~/.codex/plugins/cache" in dirs
    assert "~/.codex/vendor_imports/skills" in dirs
    assert "~/.codex/.tmp/plugins" not in dirs


def test_collect_uses_explicit_skill_dirs_for_codex_provider(tmp_path: Path) -> None:
    write_skill(tmp_path / "codex-skill", "codex-skill")

    result = collect_skills.collect(
        skill_dirs=[str(tmp_path)],
        provider="codex",
        include_project_skills=False,
    )

    assert result["summary"]["total_skills"] == 1
    assert result["skills"][0]["name"] == "codex-skill"
    assert result["skills"][0]["scope"] == "global"


def test_codex_reads_explicit_only_policy(tmp_path: Path) -> None:
    skill = tmp_path / "manual"
    write_skill(skill, "manual")
    (skill / "agents").mkdir()
    (skill / "agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
    result = collect_skills.collect([str(tmp_path)], provider="codex", include_project_skills=False)
    assert result["skills"][0]["disable_model_invocation"] is True


def test_source_policy_and_installed_copy_are_not_counted_twice(tmp_path: Path) -> None:
    source = tmp_path / "repo/agents/skills"
    installed = tmp_path / ".codex/skills"
    write_skill(source / "manual", "manual")
    write_skill(installed / "manual", "manual")
    (source.parent / "skill_rendering.json").write_text(
        json.dumps({"skills": {"manual": {"codex": {"openai": {"allow_implicit_invocation": False}}}}})
    )
    source_result = collect_skills.collect([str(source)], provider="codex", include_project_skills=False)
    assert source_result["skills"][0]["disable_model_invocation"] is True
    assert source_result["skills"][0]["scope"] == "catalog"
    result = collect_skills.collect([str(source), str(installed)], provider="codex", include_project_skills=False)
    assert result["summary"]["total_skills"] == 1
    skill = result["skills"][0]
    assert skill["scope"] == "global"
    assert len(skill["provenance"]) == 2
    assert skill["disable_model_invocation"] is False


def test_plugin_cache_is_not_evidence_of_active_visibility(tmp_path: Path) -> None:
    cache = tmp_path / ".codex/plugins/cache"
    write_skill(cache / "plugin/version/skills/helper", "helper")
    result = collect_skills.collect([str(cache)], provider="codex", include_project_skills=False)
    assert result["skills"][0]["scope"] == "catalog"
    assert result["attention_budget"]["global_description_tokens"] == 0
    assert result["limitations"]


def test_codex_project_discovery_includes_ancestor_skills_without_cross_project_leaks(tmp_path: Path) -> None:
    project = tmp_path / "project-with-hyphens"
    (project / ".git").mkdir(parents=True)
    write_skill(project / ".agents/skills/local", "local")
    write_skill(project / "child/.codex/skills/child-only", "child-only")
    write_skill(tmp_path / "other/.agents/skills/other", "other")
    found = collect_skills.discover_project_skill_dirs(provider="codex", project_paths=[str(project / "child")])
    assert set(found) == {
        (str(project / ".agents/skills"), str(project)),
        (str(project / "child/.codex/skills"), str(project / "child")),
    }


def test_same_named_project_skills_remain_separate(tmp_path: Path) -> None:
    projects = [tmp_path / "one", tmp_path / "two"]
    for project in projects:
        (project / ".git").mkdir(parents=True)
        write_skill(project / ".agents/skills/helper", "helper")
    result = collect_skills.collect(
        skill_dirs=[str(tmp_path / "absent")], provider="codex", project_paths=[str(path) for path in projects]
    )
    assert result["summary"]["total_skills"] == 2
    assert {skill["project_path"] for skill in result["skills"]} == {str(path) for path in projects}


def test_unrecognized_policy_is_reported_not_silently_assumed(tmp_path: Path) -> None:
    skill = tmp_path / "manual"
    write_skill(skill, "manual")
    (skill / "agents").mkdir()
    (skill / "agents/openai.yaml").write_text("policy: {allow_implicit_invocation: false}\n")
    result = collect_skills.collect([str(tmp_path)], provider="codex", include_project_skills=False)
    assert result["skills"][0]["policy_warning"]


def test_codex_true_policy_overrides_legacy_frontmatter(tmp_path: Path) -> None:
    skill = tmp_path / "automatic"
    write_skill(skill, "automatic")
    path = skill / "SKILL.md"
    path.write_text(path.read_text().replace("name: automatic", "name: automatic\ndisable-model-invocation: true"))
    (skill / "agents").mkdir()
    (skill / "agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: true # explicit preference\n")
    result = collect_skills.collect([str(tmp_path)], provider="codex", include_project_skills=False)
    assert result["skills"][0]["disable_model_invocation"] is False


def test_home_global_skills_are_not_rediscovered_as_project_local(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(collect_skills.Path, "home", autospec=True, return_value=tmp_path)
    write_skill(tmp_path / ".codex/skills/helper", "helper")
    write_skill(tmp_path / ".agents/skills/another", "another")
    write_skill(tmp_path / "project/.agents/skills/local", "local")
    found = collect_skills.discover_project_skill_dirs(provider="codex", project_paths=[str(tmp_path / "project")])
    assert found == [(str(tmp_path / "project/.agents/skills"), str(tmp_path / "project"))]
