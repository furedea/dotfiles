"""Generated Claude permissions and precise command rules share the same boundaries."""

import json
from pathlib import Path

import pytest

from conftest import CliRunner, HarnessRunner, REPO_ROOT


pytestmark = pytest.mark.integration
POLICY = json.loads((REPO_ROOT / "agents/command_permissions.json").read_text())
ALLOW = {tuple(rule["prefix"]) for rule in POLICY["rules"] if rule["decision"] == "allow"}
ASK = {tuple(rule["prefix"]) for rule in POLICY["rules"] if rule["decision"] == "ask"}
VERIFICATION_PREFIXES = [
    "actionlint",
    "autocorrect --lint",
    "bats",
    "bash -n",
    "cargo test",
    "cargo check",
    "cargo clippy",
    "cargo fmt --check",
    "commitlint",
    "deadnix",
    "dprint check",
    "nixfmt --check",
    "npm test",
    "npm run test",
    "npm run lint",
    "npm run format-check",
    "npm run format:check",
    "npm run typecheck",
    "node --test",
    "oxfmt --check",
    "oxlint",
    "pnpm test",
    "pnpm run test",
    "pnpm run lint",
    "pnpm run format-check",
    "pnpm run format:check",
    "pnpm run typecheck",
    "selene",
    "shellcheck",
    "shfmt -d",
    "statix",
    "stylua --check",
    "tex-fmt --check",
    "tsgolint",
    "uv run --frozen pytest",
    "uv run --frozen ruff",
    "uv run --frozen ty",
]


@pytest.fixture(scope="module")
def generated_permissions(agent_harness: HarnessRunner, tmp_path_factory: pytest.TempPathFactory) -> dict:
    path = tmp_path_factory.mktemp("claude-permissions") / "settings.json"
    agent_harness("generate-claude-settings", "--output", str(path))
    return json.loads(path.read_text())["permissions"]


def bash_prefixes(permissions: dict, decision: str) -> set[str]:
    return {value[5:-3] for value in permissions[decision] if value.startswith("Bash(") and value.endswith(":*)")}


def test_generated_runtime_permissions_are_accepted_by_the_guard(
    agent_harness: HarnessRunner, tmp_path: Path, run_cli: CliRunner
) -> None:
    path = tmp_path / "command_permissions.json"
    agent_harness("generate-command-permissions", "--output", str(path))
    result = run_cli(
        "agents/hooks/guard_command.py",
        "allowed",
        payload={"tool_input": {"command": "gh pr list"}},
        env={"AGENT_COMMAND_PERMISSIONS": str(path)},
    )
    assert result.returncode == 0, result.stderr


def test_generated_bash_allows_exactly_match_shared_allow_prefixes(generated_permissions: dict) -> None:
    assert bash_prefixes(generated_permissions, "allow") == {" ".join(prefix) for prefix in ALLOW}


def test_every_shared_allow_prefix_has_a_precise_global_rule() -> None:
    rules = json.loads((REPO_ROOT / "agents/hooks/rules/allowed_commands.json").read_text())
    patterns = [pattern for rule in rules["rules"] for pattern in rule["patterns"]]
    for prefix in ALLOW:
        start = "^" + " ".join(prefix)
        assert any(
            pattern.startswith(start + boundary) for pattern in patterns for boundary in (" ", "(", "$", r"\s")
        ), prefix


@pytest.mark.parametrize("prefix", VERIFICATION_PREFIXES)
def test_local_verification_renders_only_as_allow(generated_permissions: dict, prefix: str) -> None:
    assert tuple(prefix.split()) in ALLOW
    assert prefix in bash_prefixes(generated_permissions, "allow")
    assert prefix not in bash_prefixes(generated_permissions, "ask")


@pytest.mark.parametrize(
    "prefix",
    [
        ["uv", "run", "pytest"],
        ["uv", "run", "ruff"],
        ["uv", "run", "ty"],
        ["uv", "run", "--with", "pytest", "pytest"],
        ["uv", "run", "--frozen", "--with", "pytest", "pytest"],
    ],
)
def test_obsolete_nonfrozen_and_transient_prefix_is_absent(prefix: list[str]) -> None:
    assert all(rule["prefix"] != prefix for rule in POLICY["rules"])


def test_ask_prefix_has_no_allow_ancestor() -> None:
    for ask in ASK:
        assert not any(ask[: len(allow)] == allow for allow in ALLOW), ask
