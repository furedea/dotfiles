"""Configured targets augment discovery without hiding missing contracts."""

import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT, load_script_module

selection = load_script_module("agents/hooks/lib/verification_selection.py", "verification_selection")


def project(tmp_path: Path, mappings: dict) -> dict:
    path = tmp_path / ".agents/hooks/rules/related_test_extensions.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(mappings))
    return selection.load_defaults(REPO_ROOT / "agents/hooks/rules/related_test_defaults.json")


def test_duplicate_explicit_targets_run_once(tmp_path: Path) -> None:
    rules = project(tmp_path, {"src/**": ["tests/test_behavior.py", "tests/test_behavior.py"]})
    (tmp_path / "pyproject.toml").touch()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_behavior.py").touch()
    commands, errors = selection.language_plan(tmp_path, rules, ("src/one.py", "src/two.py"))
    assert not errors
    assert [item.arguments for item in commands] == [
        ("uv", "run", "--frozen", "pytest", "--no-header", "-q", "tests/test_behavior.py")
    ]


def test_missing_target_is_an_error_alongside_valid_targets(tmp_path: Path) -> None:
    rules = project(tmp_path, {"config.json": ["tests/test_behavior.py", "tests/missing.py"]})
    (tmp_path / "pyproject.toml").touch()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_behavior.py").touch()
    commands, errors = selection.language_plan(tmp_path, rules, ("config.json",))
    assert len(commands) == 1
    assert errors == ["Configured test target does not exist: tests/missing.py"]


def test_bats_directory_mapping_is_non_recursive_and_deduplicated(tmp_path: Path) -> None:
    rules = project(tmp_path, {"config.json": ["tests/hooks", "tests/hooks/direct.bats"]})
    (tmp_path / "tests/hooks/nested").mkdir(parents=True)
    (tmp_path / "tests/hooks/direct.bats").touch()
    (tmp_path / "tests/hooks/nested/other.bats").touch()
    commands, errors = selection.language_plan(tmp_path, rules, ("config.json",))
    assert not errors
    assert [item.arguments for item in commands] == [("bats", "tests/hooks/direct.bats")]


def test_javascript_without_a_test_command_is_not_success(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "package.json").write_text("{}")
    with pytest.raises(selection.UnknownTestCommand):
        selection.language_plan(tmp_path, rules, ("src/file.ts",))
