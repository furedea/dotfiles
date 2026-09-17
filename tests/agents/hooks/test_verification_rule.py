"""Repository test mappings retain every required consumer and existing target."""

import json
from pathlib import Path

import pytest

from tests.runtime import REPO_ROOT


RULES = REPO_ROOT / ".agents/hooks/rules/related_test_extensions.json"
DEFAULTS = REPO_ROOT / "agents/hooks/rules/related_test_defaults.json"


@pytest.fixture
def extension() -> dict[str, list[str]]:
    return json.loads(RULES.read_text())


@pytest.mark.parametrize("path", [RULES, DEFAULTS])
def test_rule_file_is_a_json_object(path: Path) -> None:
    assert isinstance(json.loads(path.read_text()), dict)


def test_defaults_define_repository_test_conventions() -> None:
    rules = json.loads(DEFAULTS.read_text())
    assert set(rules) == {"bats", "python", "rust", "javascript_typescript"}
    assert rules["bats"]["source_extensions"] == [".sh", ".bats"]
    assert {"{stem}.bats", "test_{stem}.bats"} <= set(rules["bats"]["test_patterns"])
    assert rules["python"]["source_extensions"] == [".py"]
    assert {"test_{stem}.py", "{stem}_test.py"} <= set(rules["python"]["test_patterns"])
    assert "pyproject.toml" in rules["python"]["project_markers"]
    assert rules["rust"]["source_extensions"] == [".rs"]
    assert "Cargo.toml" in rules["rust"]["project_markers"]
    assert rules["rust"]["integration_test_dir"] == "tests"
    assert "src" in rules["rust"]["source_dirs"]
    assert rules["javascript_typescript"]["source_extensions"] == [".js", ".jsx", ".ts", ".tsx"]
    assert "{stem}.test.ts" in rules["javascript_typescript"]["test_patterns"]


def test_defaults_have_no_obsolete_lint_entry_point() -> None:
    assert all("lint_hook" not in rule for rule in json.loads(DEFAULTS.read_text()).values())


def test_codex_verifies_changes_before_stopping() -> None:
    hooks = json.loads((REPO_ROOT / "agents/hooks.json").read_text())
    commands = [hook["command"] for group in hooks["codex"]["hooks"]["Stop"] for hook in group["hooks"]]
    assert '"$HOME/.claude/hooks/verification_session.py" codex stop' in commands


def test_extension_values_are_nonempty_arrays_of_paths(extension: dict[str, list[str]]) -> None:
    assert extension
    for source, targets in extension.items():
        assert isinstance(targets, list) and targets, source
        assert all(isinstance(target, str) and target for target in targets), source


def test_every_extension_target_exists(extension: dict[str, list[str]]) -> None:
    missing = {target for targets in extension.values() for target in targets if not (REPO_ROOT / target).exists()}
    assert not missing


@pytest.mark.parametrize("source", ["flake.nix", "flake.lock", "nix/**"])
def test_nix_changes_select_configuration_and_packaged_runtime_contracts(
    extension: dict[str, list[str]], source: str
) -> None:
    assert {
        "tests/nix/configuration.bats",
        "tests/agents/agent_hook.bats",
        "tests/agents/codex/codex_notification.bats",
        "tests/herdr/herdr_command.bats",
        "tests/hermes/hermes_secretary.bats",
        "tests/terminal-browser/terminal_browser.bats",
        "tests/hermes/test_hermes_gateway.py",
    } <= set(extension[source])


@pytest.mark.parametrize(
    ("source", "required"),
    [
        ("agents/hooks/audit_log.py", {"test_allowed_command.py", "test_guard_git.py"}),
        ("agents/hooks/lib/shell_syntax.py", {"test_allowed_command.py", "test_hook_adapter_cli.py"}),
        ("agents/hooks/lint_format.py", {"test_lint_format_cli.py", "test_hook_adapter_cli.py"}),
        ("agents/hooks/guard_file.py", {"test_secret_content.py", "test_hook_adapter_cli.py"}),
        (
            "agents/hooks/rules/secret_content_patterns.json",
            {"test_secret_content.py", "test_secret_content_pattern.py"},
        ),
        ("tests/agents/hooks/secret_content_samples.json", {"test_secret_content.py"}),
        ("agents/hooks/rules/secret_commit_policy.json", {"test_guard_file.py", "test_secret_commit_policy.py"}),
        ("agents/hooks/rules/secret_path_policy.json", {"test_hook_adapter_cli.py"}),
        ("agents/claude/settings.json", {"test_allowed_command.py", "test_notification.py"}),
        ("agents/codex/config.toml", {"test_notification.py"}),
        (
            "agents/hooks.json",
            {
                "test_notification.py",
                "test_verification_rule.py",
                "test_python_runtime.py",
                "test_verification_session.py",
            },
        ),
        ("bash/.bashrc", {"configuration.bats"}),
        ("zsh/.zshrc", {"configuration.bats"}),
        (
            "agents/command_permissions.json",
            {
                "test_execpolicy.py",
                "test_command_permission_sync.py",
                "test_allowed_command.py",
                "test_forbidden_command.py",
            },
        ),
        ("agents/hooks/rules/allowed_commands.json", {"test_command_permission_sync.py", "test_allowed_command.py"}),
        ("agents/hooks/rules/forbidden_commands.json", {"test_forbidden_command.py"}),
        ("herdr/config.toml", {"test_popup_command.py"}),
        ("herdr/reviewr.toml", {"test_popup_command.py"}),
        ("nvim/init.lua", {"test_nvim_plugin_lock.py"}),
        ("nvim/lazy-lock.json", {"test_nvim_plugin_lock.py"}),
        (".gitignore", {"test_nvim_plugin_lock.py"}),
        ("git/ignore", {"test_nvim_plugin_lock.py"}),
        ("hermes/secretary/skills/secretary/**", {"test_secretary_skill.py"}),
        ("tests/hermes/gateway_probe.py", {"test_hermes_gateway.py"}),
        (
            ".agents/hooks/rules/related_test_extensions.json",
            {"test_verification_rule.py", "test_check_selection.py"},
        ),
    ],
)
def test_shared_inputs_select_their_consumers(
    extension: dict[str, list[str]], source: str, required: set[str]
) -> None:
    assert required <= {Path(target).name for target in extension[source]}
