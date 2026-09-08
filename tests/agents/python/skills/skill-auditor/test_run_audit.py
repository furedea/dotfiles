from pathlib import Path
import pytest
from pytest_mock import MockerFixture

from tests.agents.python.conftest import load_script_module


run_audit = load_script_module(
    "agents/skills/skill-auditor/scripts/run_audit.py",
    "skill_auditor_run_audit",
)


def test_default_base_dir_uses_user_provider_store_with_project_slug(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    project = repo / "agents" / "skills" / "skill-auditor"
    project.mkdir(parents=True)
    (repo / ".git").mkdir()

    base_dir = run_audit.default_base_dir("codex", str(project))

    expected_slug = f"{repo.parent.name}-repo-agents-skills-skill-auditor"
    assert base_dir == Path("~/.codex/skill-report").expanduser() / "projects" / expected_slug


def test_default_base_dir_uses_root_slug_for_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    base_dir = run_audit.default_base_dir("codex", str(repo))

    expected_slug = f"{repo.parent.name}-repo"
    assert base_dir == Path("~/.codex/skill-report").expanduser() / "projects" / expected_slug


def test_build_batches_marks_disable_model_invocation_skills() -> None:
    transcripts = {
        "sessions": [
            {"project_dir": "/tmp/project"},
            {"project_dir": "/tmp/project"},
        ]
    }
    manifest = {
        "skills": [
            {
                "name": "global-skill",
                "scope": "global",
                "disable_model_invocation": False,
            },
            {
                "name": "explicit-skill",
                "scope": "global",
                "disable_model_invocation": True,
            },
        ]
    }

    batches = run_audit.build_batches(transcripts, manifest, batch_size=60, max_batches=12)

    assert batches == [
        {
            "session_indices": [0, 1],
            "label": "global-only (mixed projects)",
            "visible_skill_names": ["global-skill", "explicit-skill"],
            "batch_index": 0,
            "dmi_skill_names": ["explicit-skill"],
        }
    ]


def test_merge_audit_reports_recalculates_skill_accuracy() -> None:
    reports = [
        {
            "skill_reports": [
                {
                    "skill_name": "python-style",
                    "skill_path": "/skills/python-style/SKILL.md",
                    "description_excerpt": "Python",
                    "stats": {
                        "total_fires": 1,
                        "correct_fires": 1,
                        "false_positives": 0,
                        "false_negatives": 0,
                        "accuracy": 1.0,
                    },
                    "incidents": [],
                    "health_assessment": "Healthy",
                    "suggested_fix": None,
                }
            ],
            "skills_never_fired": [],
            "competition_pairs": [],
            "coverage_gaps": [],
            "meta": {
                "sessions_analyzed": 1,
                "turns_analyzed": 2,
                "turns_with_skill_activity": 1,
                "turns_no_skill_needed": 1,
                "skills_in_scope": 1,
            },
        },
        {
            "skill_reports": [
                {
                    "skill_name": "python-style",
                    "skill_path": "/skills/python-style/SKILL.md",
                    "description_excerpt": "Python",
                    "stats": {
                        "total_fires": 1,
                        "correct_fires": 0,
                        "false_positives": 1,
                        "false_negatives": 0,
                        "accuracy": 0.0,
                    },
                    "incidents": [{"verdict": "false_positive"}],
                    "health_assessment": "Needs attention",
                    "suggested_fix": "Add exclusion.",
                }
            ],
            "skills_never_fired": [],
            "competition_pairs": [],
            "coverage_gaps": [],
            "meta": {
                "sessions_analyzed": 1,
                "turns_analyzed": 3,
                "turns_with_skill_activity": 1,
                "turns_no_skill_needed": 2,
                "skills_in_scope": 1,
            },
        },
    ]

    merged = run_audit.merge_audit_reports(reports)

    report = merged["skill_reports"][0]
    assert report["stats"]["total_fires"] == 2
    assert report["stats"]["correct_fires"] == 1
    assert report["stats"]["accuracy"] == 0.5
    assert report["suggested_fix"] == "Add exclusion."
    assert merged["meta"]["turns_analyzed"] == 5


def test_merge_audit_reports_counts_each_competition_incident_once() -> None:
    reports = [
        {"competition_pairs": [{"skill_a": "python", "skill_b": "review", "incidents": 2}]},
        {"competition_pairs": [{"skill_a": "review", "skill_b": "python", "incidents": 3}]},
    ]

    merged = run_audit.merge_audit_reports(reports)

    assert len(merged["competition_pairs"]) == 1
    assert merged["competition_pairs"][0]["incidents"] == 5
    assert reports[0]["competition_pairs"][0]["incidents"] == 2


def test_merge_audit_reports_counts_each_coverage_gap_occurrence_once() -> None:
    reports = [
        {"coverage_gaps": [{"unmet_intent": "review", "frequency": 2, "related_sessions": ["a"]}]},
        {"coverage_gaps": [{"unmet_intent": "review", "frequency": 3, "related_sessions": ["b", "a"]}]},
    ]

    merged = run_audit.merge_audit_reports(reports)

    assert merged["coverage_gaps"] == [{"unmet_intent": "review", "frequency": 5, "related_sessions": ["a", "b"]}]
    assert reports[0]["coverage_gaps"][0] == {
        "unmet_intent": "review",
        "frequency": 2,
        "related_sessions": ["a"],
    }


def test_write_agent_prompts_includes_the_requested_language_in_every_prompt(tmp_path: Path) -> None:
    batches = [
        {
            "batch_index": 0,
            "session_indices": [0],
            "visible_skill_names": ["python-style"],
            "dmi_skill_names": [],
        }
    ]

    run_audit.write_agent_prompts(tmp_path, batches, "Japanese")

    prompt_paths = (
        tmp_path / "agent-prompts" / "routing_batch_0.md",
        tmp_path / "agent-prompts" / "portfolio_analysis.md",
        tmp_path / "agent-prompts" / "improvement_plan.md",
    )
    for prompt_path in prompt_paths:
        instruction = prompt_path.read_text(encoding="utf-8").split("\n\n", maxsplit=1)[0]
        assert "Japanese" in instruction


@pytest.mark.parametrize(
    "cwd, expected",
    [
        ("/tmp/project/subdir", ["local"]),
        ("/tmp/project-other", []),
        ("-tmp-project", ["local"]),
        ("-tmp-project-other", []),
        ("-something-tmp-project", []),
    ],
)
def test_local_skill_matching_respects_directory_boundaries(cwd: str, expected: list[str]) -> None:
    skills = [{"name": "local", "scope": "project-local", "project_path": "/tmp/project"}]
    assert run_audit.local_skill_names(cwd, skills) == expected


def test_prepare_passes_observed_project_directories_to_inventory(tmp_path: Path, mocker: MockerFixture) -> None:
    transcripts = {"sessions": [{"project_dir": "/tmp/project/sub"}]}
    mocker.patch.object(run_audit.collect_transcripts, "collect", autospec=True, return_value=transcripts)
    inventory = mocker.patch.object(run_audit.collect_skills, "collect", autospec=True, return_value={"skills": []})
    mocker.patch.object(run_audit, "print_collection_summary", autospec=True)
    config = run_audit.RunConfig("codex", "all", 14, 1, "Japanese", None, tmp_path, 60, 12)
    run_audit.prepare_run(config)
    inventory.assert_called_once_with(provider="codex", project_paths=["/tmp/project/sub"])


def test_merge_preserves_unassessable_accuracy_and_counts_each_incident_once() -> None:
    report = {
        "skill_reports": [{"skill_name": "helper", "stats": {"total_fires": 0, "accuracy": None}}],
        "competition_pairs": [{"skill_a": "one", "skill_b": "two", "incidents": 2}],
        "coverage_gaps": [{"unmet_intent": "intent", "frequency": 3}],
    }
    merged = run_audit.merge_audit_reports([report, report])
    assert merged["skill_reports"][0]["stats"]["accuracy"] is None
    assert merged["competition_pairs"][0]["incidents"] == 4
    assert merged["coverage_gaps"][0]["frequency"] == 6


def test_routing_prompt_requires_historical_evidence_not_current_inventory(tmp_path: Path) -> None:
    batch = {"session_indices": [0], "visible_skill_names": ["helper"], "dmi_skill_names": [], "batch_index": 0}
    prompt = run_audit.routing_prompt(tmp_path, batch, "Japanese")
    assert "CURRENT inventory candidates" in prompt
    assert "historical visibility" in prompt
    assert "accuracy: null" in prompt


def test_catalog_only_skills_are_excluded_from_routing_candidates() -> None:
    manifest = {"skills": [{"name": "cached", "scope": "catalog"}]}
    batches = run_audit.build_batches({"sessions": [{"project_dir": "/tmp/project"}]}, manifest)
    assert batches[0]["visible_skill_names"] == []


def test_merge_does_not_turn_selected_examples_into_population_accuracy() -> None:
    observed = {
        "skill_reports": [
            {
                "skill_name": "helper",
                "stats": {
                    "total_fires": 1,
                    "correct_fires": 1,
                    "false_positives": 0,
                    "false_negatives": 0,
                    "accuracy": 1.0,
                },
            }
        ]
    }
    unassessable = {
        "skill_reports": [
            {
                "skill_name": "helper",
                "stats": {
                    "total_fires": 0,
                    "correct_fires": 0,
                    "false_positives": 0,
                    "false_negatives": 0,
                    "accuracy": None,
                },
            }
        ]
    }
    merged = run_audit.merge_audit_reports([observed, unassessable])
    assert merged["skill_reports"][0]["stats"]["correct_fires"] == 1
    assert merged["skill_reports"][0]["stats"]["accuracy"] is None
