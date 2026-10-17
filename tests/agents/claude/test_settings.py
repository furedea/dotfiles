"""Claude session settings shape the environment every agent command and hook inherits."""

import json

from tests.runtime import REPO_ROOT


def test_agent_git_commands_run_without_the_sandboxed_fsmonitor_daemon() -> None:
    environment = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["env"]
    count = int(environment["GIT_CONFIG_COUNT"])
    configured = {
        environment[f"GIT_CONFIG_KEY_{index}"]: environment[f"GIT_CONFIG_VALUE_{index}"] for index in range(count)
    }
    assert configured["core.fsmonitor"] == "false"


def test_commands_run_sandboxed_by_default() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert sandbox["enabled"] is True


def test_verification_and_agent_tools_work_without_escaping_the_sandbox() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert {
        "~/.cache/nix",
        "~/.cache/uv",
        "~/Library/Caches/dprint",
        "~/.local/state/agent-harness",
    } <= set(sandbox["filesystem"]["allowWrite"])
    assert {"gh *", "herdr *"} <= set(sandbox["excludedCommands"])


def test_excluded_commands_match_invocations_with_arguments() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert [command for command in sandbox["excludedCommands"] if not command.endswith(" *")] == []


def test_sandbox_paths_use_the_home_prefix_the_sandbox_expands() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert [path for path in sandbox["filesystem"]["allowWrite"] if "$" in path] == []


def test_go_clis_can_verify_tls_inside_the_sandbox() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert sandbox["enableWeakerNetworkIsolation"] is True


def test_agent_git_and_its_hooks_run_inside_the_sandbox() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert [command for command in sandbox["excludedCommands"] if command.startswith("git ")] == []


def test_agent_commits_and_tags_are_left_unsigned() -> None:
    environment = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["env"]
    count = int(environment["GIT_CONFIG_COUNT"])
    configured = {
        environment[f"GIT_CONFIG_KEY_{index}"]: environment[f"GIT_CONFIG_VALUE_{index}"] for index in range(count)
    }
    assert configured["commit.gpgsign"] == "false"
    assert configured["tag.gpgsign"] == "false"


def test_no_command_escapes_the_sandbox_except_the_excluded_tools() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert sandbox["allowUnsandboxedCommands"] is False


def test_nix_reaches_its_daemon_from_inside_the_sandbox() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert sandbox["network"]["allowUnixSockets"] == ["/nix/var/nix/daemon-socket/socket"]


def test_nix_resolves_the_flake_registry_from_inside_the_sandbox() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert {"channels.nixos.org"} <= set(sandbox["network"]["allowedDomains"])


def test_pnpm_installs_into_its_shared_store_from_inside_the_sandbox() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert {"~/.local/share/pnpm"} <= set(sandbox["filesystem"]["allowWrite"])


def test_dev_servers_and_end_to_end_tests_can_listen_on_local_ports() -> None:
    sandbox = json.loads((REPO_ROOT / "agents/claude/settings.json").read_text())["sandbox"]
    assert sandbox["network"]["allowLocalBinding"] is True
