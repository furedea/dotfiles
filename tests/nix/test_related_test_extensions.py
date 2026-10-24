"""Repository test mappings retain every required consumer and existing target."""

import json
from pathlib import Path

import pytest

from tests.runtime import REPO_ROOT


RULES = REPO_ROOT / ".agents/hooks/rules/related_test_extensions.json"


@pytest.fixture
def extension() -> dict[str, list[str]]:
    return json.loads(RULES.read_text())


def test_rule_file_is_a_json_object() -> None:
    assert isinstance(json.loads(RULES.read_text()), dict)


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
        "tests/nix/agent_hook.bats",
        "tests/nix/codex_notification.bats",
        "tests/herdr/herdr_command.bats",
        "tests/hermes/hermes_secretary.bats",
        "tests/terminal-browser/terminal_browser.bats",
        "tests/hermes/test_hermes_gateway.py",
    } <= set(extension[source])


@pytest.mark.parametrize(
    ("source", "required"),
    [
        ("bash/.bashrc", {"configuration.bats"}),
        ("zsh/.zshrc", {"configuration.bats"}),
        ("herdr/config.toml", {"test_popup_command.py"}),
        ("herdr/reviewr.toml", {"test_popup_command.py"}),
        ("nvim/init.lua", {"test_nvim_plugin_lock.py"}),
        ("nvim/lazy-lock.json", {"test_nvim_plugin_lock.py"}),
        (".gitignore", {"test_nvim_plugin_lock.py"}),
        ("git/ignore", {"test_nvim_plugin_lock.py"}),
        ("hermes/secretary/skills/secretary/**", {"test_secretary_skill.py"}),
        ("tests/hermes/gateway_probe.py", {"test_hermes_gateway.py"}),
        (".agents/hooks/rules/related_test_extensions.json", {"test_related_test_extensions.py"}),
    ],
)
def test_shared_inputs_select_their_consumers(
    extension: dict[str, list[str]], source: str, required: set[str]
) -> None:
    assert required <= {Path(target).name for target in extension[source]}
