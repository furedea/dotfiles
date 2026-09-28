"""Configured targets augment discovery without hiding missing contracts."""

import json
from pathlib import Path

import pytest

from tests.runtime import REPO_ROOT, load_script_module

selection = load_script_module("agents/hooks/lib/check_selection.py", "check_selection")


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


def test_sources_mapped_to_another_language_run_only_that_language(tmp_path: Path) -> None:
    rules = project(tmp_path, {"src/assets/**": ["src/bridges.rs", "tests/artifacts.rs"]})
    (tmp_path / "package.json").write_text(json.dumps({"devDependencies": {"@openai/codex": "1.0.0"}}))
    touch_all(tmp_path, ["Cargo.toml", "src/bridges.rs", "tests/artifacts.rs"])
    commands, errors = selection.language_plan(tmp_path, rules, ("src/assets/pi/hook_bridge.ts",))
    assert not errors
    assert [item.arguments for item in commands] == [
        ("cargo", "test", "bridges", "--quiet"),
        ("cargo", "test", "--test", "artifacts", "--quiet"),
    ]


def test_unmapped_sources_beside_mapped_ones_still_require_their_runner(tmp_path: Path) -> None:
    rules = project(tmp_path, {"src/assets/**": ["tests/artifacts.rs"]})
    (tmp_path / "package.json").write_text("{}")
    touch_all(tmp_path, ["Cargo.toml", "tests/artifacts.rs"])
    with pytest.raises(selection.UnknownTestCommand):
        selection.language_plan(tmp_path, rules, ("src/assets/bridge.ts", "src/app.ts"))


PYTEST = ("uv", "run", "--frozen", "pytest", "--no-header", "-q")


@pytest.mark.parametrize("changed", ["pyproject.toml", "uv.lock", "pytest.ini", "conftest.py", "tests/conftest.py"])
def test_python_configuration_changes_select_the_full_suite(tmp_path: Path, changed: str) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "pyproject.toml").touch()
    commands, errors = selection.language_plan(tmp_path, rules, (changed,))
    assert not errors
    assert [item.arguments for item in commands] == [PYTEST]
    assert commands[0].scope == "full suite"


def test_configuration_changes_do_not_degrade_to_partial_tests(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    touch_all(tmp_path, ["pyproject.toml", "src/app.py", "tests/test_app.py"])
    commands, errors = selection.language_plan(tmp_path, rules, ("uv.lock", "src/app.py"))
    assert not errors
    assert [item.arguments for item in commands] == [PYTEST]
    assert commands[0].scope == "full suite"


def test_deleted_project_marker_is_reported_instead_of_passing(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    commands, errors = selection.language_plan(tmp_path, rules, ("pyproject.toml",))
    assert not commands
    assert errors and "pyproject.toml" in errors[0]


def test_deleted_configuration_still_selects_the_full_suite(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "pyproject.toml").touch()
    commands, errors = selection.language_plan(tmp_path, rules, ("uv.lock",))
    assert not errors
    assert [item.arguments for item in commands] == [PYTEST]


def test_unmatched_sources_escalate_beyond_partial_matches(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    touch_all(tmp_path, ["pyproject.toml", "tests/test_a.py"])
    commands, errors = selection.language_plan(tmp_path, rules, ("a.py", "b.py"))
    assert not errors
    assert [item.arguments for item in commands] == [PYTEST]
    assert commands[0].scope == "full suite"


def test_mapped_sources_stay_within_their_declared_targets(tmp_path: Path) -> None:
    rules = project(tmp_path, {"lib/core.py": ["tests/unit/test_core.py"]})
    touch_all(tmp_path, ["pyproject.toml", "tests/unit/test_core.py"])
    commands, errors = selection.language_plan(tmp_path, rules, ("lib/core.py",))
    assert not errors
    assert [item.arguments for item in commands] == [(*PYTEST, "tests/unit/test_core.py")]


def test_sources_without_a_project_marker_report_instead_of_passing(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    commands, errors = selection.language_plan(tmp_path, rules, ("script.py",))
    assert not commands
    assert errors and "pyproject.toml" in errors[0]


def test_shell_sources_without_a_test_directory_report_instead_of_passing(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    commands, errors = selection.language_plan(tmp_path, rules, ("script.sh",))
    assert not commands
    assert errors and "tests" in errors[0]


def test_plain_documents_do_not_select_the_full_suite(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "pyproject.toml").touch()
    commands, errors = selection.language_plan(tmp_path, rules, ("docs/guide.md",))
    assert not commands
    assert not errors


@pytest.mark.parametrize(
    "changed",
    ["package.json", "tsconfig.json", "src/tsconfig.json", "jest.config.js", "vitest.config.ts", "pnpm-lock.yaml"],
)
def test_javascript_configuration_changes_select_the_full_suite(tmp_path: Path, changed: str) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "node --test"}}))
    commands, errors = selection.language_plan(tmp_path, rules, (changed,))
    assert not errors
    assert [item.arguments for item in commands] == [("node", "--test")]
    assert commands[0].scope == "full suite"


def test_javascript_unmatched_sources_escalate_without_dependency_analysis(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"jest": "30"}, "scripts": {"test": "jest"}})
    )
    touch_all(tmp_path, ["src/util.js", "tests/util.test.js"])
    commands, errors = selection.language_plan(tmp_path, rules, ("src/util.js", "src/helper.js"))
    assert not errors
    assert [item.arguments for item in commands] == [("npm", "exec", "--", "jest")]
    assert commands[0].scope == "full suite"


@pytest.mark.parametrize("changed", ["Cargo.toml", "Cargo.lock", "rust-toolchain", "rust-toolchain.toml"])
def test_rust_configuration_changes_select_the_full_suite(tmp_path: Path, changed: str) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "Cargo.toml").touch()
    commands, errors = selection.language_plan(tmp_path, rules, (changed,))
    assert not errors
    assert [item.arguments for item in commands] == [("cargo", "test", "--quiet")]
    assert commands[0].scope == "full suite"


def test_rust_unmatched_sources_escalate_beyond_named_targets(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    touch_all(tmp_path, ["Cargo.toml", "src/parser.rs", "src/util.rs", "tests/parser.rs"])
    commands, errors = selection.language_plan(tmp_path, rules, ("src/parser.rs", "src/util.rs"))
    assert not errors
    assert [item.arguments for item in commands] == [("cargo", "test", "--quiet")]
    assert commands[0].scope == "full suite"


def touch_all(root: Path, names: list[str]) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


def test_declared_pytest_testpaths_keep_stray_test_copies_out(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    touch_all(tmp_path, ["tests/test_app.py", "experiments/runtime/tests/test_app.py"])
    commands, errors = selection.language_plan(tmp_path, rules, ("app.py", "experiments/runtime/tests/test_app.py"))
    assert not errors
    assert [item.arguments for item in commands] == [(*PYTEST, "tests/test_app.py")]


def test_explicit_targets_outside_declared_testpaths_still_run(tmp_path: Path) -> None:
    rules = project(tmp_path, {"app.py": ["experiments/checks/test_extra.py"]})
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    touch_all(tmp_path, ["tests/test_app.py", "experiments/checks/test_extra.py"])
    commands, errors = selection.language_plan(tmp_path, rules, ("app.py",))
    assert not errors
    assert [item.arguments for item in commands] == [
        (*PYTEST, "experiments/checks/test_extra.py", "tests/test_app.py")
    ]


def test_cache_and_build_directories_are_not_searched_for_tests(tmp_path: Path) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "pyproject.toml").touch()
    touch_all(tmp_path, ["tests/test_app.py", ".cache/snapshot/tests/test_app.py", "build/lib/tests/test_app.py"])
    commands, errors = selection.language_plan(tmp_path, rules, ("app.py",))
    assert not errors
    assert [item.arguments for item in commands] == [(*PYTEST, "tests/test_app.py")]


@pytest.mark.parametrize(
    "changed,files,mappings,expected",
    [
        ("script.sh", ["tests/script.bats", "tests/other.bats"], {}, [("bats", "tests/script.bats")]),
        ("script.sh", ["tests/test_script.bats", "tests/other.bats"], {}, [("bats", "tests/test_script.bats")]),
        ("unrelated.sh", ["tests/other.bats"], {}, [("bats", "tests/", "--recursive")]),
        ("tests/changed.bats", ["tests/changed.bats", "tests/other.bats"], {}, [("bats", "tests/changed.bats")]),
        (
            "lib/shared.sh",
            ["tests/fan_out.bats", "tests/other.bats"],
            {"lib/shared.sh": ["tests/fan_out.bats"]},
            [("bats", "tests/fan_out.bats")],
        ),
        (
            "script.sh",
            ["tests/script.bats", "tests/extra.bats"],
            {"script.sh": ["tests/extra.bats"]},
            [("bats", "tests/extra.bats", "tests/script.bats")],
        ),
        (
            "config/app.toml",
            ["tests/config_check.bats"],
            {"config/*.toml": ["tests/config_check.bats"]},
            [("bats", "tests/config_check.bats")],
        ),
        ("nix/module.nix", ["tests/nix/module.bats"], {"nix/**": ["tests/nix"]}, [("bats", "tests/nix/module.bats")]),
        (
            "app.py",
            ["pyproject.toml", "tests/test_app.py", "tests/test_other.py"],
            {"app.py": ["./tests/test_app.py"]},
            [("uv", "run", "--frozen", "pytest", "--no-header", "-q", "tests/test_app.py")],
        ),
        (
            "service.py",
            ["pyproject.toml", "tests/service_test.py"],
            {},
            [("uv", "run", "--frozen", "pytest", "--no-header", "-q", "tests/service_test.py")],
        ),
        ("tests/parser.rs", ["Cargo.toml", "tests/parser.rs"], {}, [("cargo", "test", "--test", "parser", "--quiet")]),
        ("src/parser.rs", ["Cargo.toml", "tests/parser.rs"], {}, [("cargo", "test", "--test", "parser", "--quiet")]),
        ("src/parser.rs", ["Cargo.toml", "tests/other.rs"], {}, [("cargo", "test", "--quiet")]),
        ("src/lib.rs", ["Cargo.toml"], {}, [("cargo", "test", "--quiet")]),
        (
            "nix/module.nix",
            ["Cargo.toml", "tests/claude_materialization.rs"],
            {"nix/*.nix": ["tests/claude_materialization.rs"]},
            [("cargo", "test", "--test", "claude_materialization", "--quiet")],
        ),
    ],
)
def test_default_conventions_and_project_fanout(
    tmp_path: Path, changed: str, files: list[str], mappings: dict, expected: list[tuple[str, ...]]
) -> None:
    rules = project(tmp_path, mappings)
    for name in [changed, *files]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    commands, errors = selection.language_plan(tmp_path, rules, (changed,))
    assert not errors
    assert [item.arguments for item in commands] == expected


@pytest.mark.parametrize(
    "package,target,source,expected",
    [
        (
            {"packageManager": "pnpm@10", "devDependencies": {"vitest": "1"}, "scripts": {"test": "vitest run"}},
            "tests/app.test.ts",
            "src/app.ts",
            [
                ("pnpm", "exec", "vitest", "run", "tests/app.test.ts"),
                ("pnpm", "exec", "vitest", "related", "--run", "--passWithNoTests", "src/app.ts"),
            ],
        ),
        (
            {"packageManager": "pnpm@10", "devDependencies": {"vitest": "1"}},
            "tests/other.test.ts",
            "src/app.ts",
            [("pnpm", "exec", "vitest", "related", "--run", "--passWithNoTests", "src/app.ts")],
        ),
        (
            {"packageManager": "pnpm@10", "scripts": {"test": "custom-test-runner"}},
            "",
            "src/app.ts",
            [("pnpm", "test")],
        ),
        (
            {"packageManager": "npm@11", "devDependencies": {"jest": "30"}, "scripts": {"test": "jest"}},
            "tests/app.spec.js",
            "src/app.js",
            [("npm", "exec", "--", "jest", "tests/app.spec.js")],
        ),
        (
            {"scripts": {"test": "node --test"}},
            "tests/app.test.js",
            "src/app.js",
            [("node", "--test", "tests/app.test.js")],
        ),
    ],
)
def test_javascript_selects_named_and_dependency_aware_tests(
    tmp_path: Path, package: dict, target: str, source: str, expected: list[tuple[str, ...]]
) -> None:
    rules = project(tmp_path, {})
    (tmp_path / "package.json").write_text(json.dumps(package))
    for name in filter(None, (source, target)):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    commands, errors = selection.language_plan(tmp_path, rules, (source,))
    assert not errors
    assert [item.arguments for item in commands] == expected
