"""A session may drive only the Herdr agents it started; other panes may be the user's."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
from pytest_mock import MockerFixture

from tests.runtime import REPO_ROOT
from tests.agents.hooks.herdr_runtime import after, decision, hook, run, set_agents, start_agent


sys.path.insert(0, str(REPO_ROOT / "agents/hooks/lib"))
import session_store as store
import herdr_ownership


def test_a_session_prompts_the_agent_it_started(repository: Path, herdr: Path) -> None:
    start_agent(repository, herdr, "w1")
    assert decision(run(repository, "herdr agent prompt lane-a 'Implement #181' --wait")) == "allow"


def test_a_session_prompts_the_sonnet_agent_it_started(repository: Path, herdr: Path) -> None:
    start = "herdr agent start lane-a --kind claude --pane w1:p2 -- --model sonnet --effort medium"
    assert decision(run(repository, start)) == "allow"
    start_agent(repository, herdr, "w1", command=start)
    assert decision(run(repository, "herdr agent prompt lane-a 'Implement #181' --wait")) == "allow"


@pytest.mark.parametrize(
    "target", ["reviewer", "w1:p2", "$AGENT"], ids=["another name", "a pane id", "a run-time target"]
)
def test_prompting_an_agent_the_session_did_not_start_asks(repository: Path, herdr: Path, target: str) -> None:
    start_agent(repository, herdr, "w1")
    output = run(repository, f"herdr agent prompt {target} 'rm -rf ~'")
    assert decision(output) == "ask"
    assert "not started by this session" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_name_another_agent_already_holds_is_not_claimed(repository: Path, herdr: Path) -> None:
    set_agents(herdr, "reviewer\n")
    assert decision(run(repository, "herdr agent start reviewer --kind claude --pane w1:p2")) == "ask"
    set_agents(herdr, "")
    assert decision(run(repository, "herdr agent prompt reviewer 'hello'")) == "ask"


def test_ownership_belongs_to_one_session(repository: Path, herdr: Path) -> None:
    start_agent(repository, herdr, "w1")
    store.register(repository, "codex", "other")
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(hook), "codex", "pre-tool-use"],
        input=json.dumps(
            {
                "cwd": str(repository),
                "session_id": "other",
                "tool_name": "Bash",
                "tool_input": {"command": "herdr agent prompt lane-a 'hello'"},
            }
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert decision(json.loads(result.stdout)) == "ask"


def test_renaming_asks_so_an_owned_name_cannot_move_to_another_pane(repository: Path, herdr: Path) -> None:
    start_agent(repository, herdr, "w1")
    assert decision(run(repository, "herdr agent rename w1:p9 lane-a")) == "ask"


@pytest.mark.parametrize("command", ["herdr agent list", "herdr pane list", "echo herdr agent prompt reviewer"])
def test_other_herdr_commands_are_not_the_ownership_checks_concern(
    repository: Path, herdr: Path, command: str
) -> None:
    assert decision(run(repository, command)) == "allow"


@pytest.mark.parametrize(
    ("command", "plain_decision"),
    [
        ("herdr worktree remove --workspace w9", "ask"),
        ("herdr agent prompt lane-a 'hello'", "allow"),
        ("herdr agent rename w9:p2 lane-a", "ask"),
        ("herdr agent start lane-b --kind claude --pane w9:p2", "allow"),
    ],
)
@pytest.mark.parametrize(
    "form",
    [
        "HERDR_SOCKET_PATH=/tmp/other.sock {}",
        "env HERDR_SOCKET_PATH=/tmp/other.sock {}",
        "{}; echo done",
        "({})",
        "{} | cat",
        "{} > /dev/null",
        "/usr/local/bin/{}",
    ],
)
def test_ownership_actions_require_one_simple_direct_call(
    repository: Path, herdr: Path, command: str, plain_decision: str, form: str
) -> None:
    start_agent(repository, herdr, "w9")
    set_agents(herdr, "lane-a w9\n")
    output = run(repository, form.format(command))
    assert decision(output) == "ask"
    assert "one simple direct Herdr call" in output["hookSpecificOutput"]["permissionDecisionReason"]
    assert decision(run(repository, command)) == plain_decision


def test_an_ownership_action_asks_when_its_simple_command_shape_cannot_be_parsed(
    repository: Path, herdr: Path, mocker: MockerFixture
) -> None:
    start_agent(repository, herdr, "w9")
    set_agents(herdr, "lane-a w9\n")
    mocker.patch.object(
        herdr_ownership.shell_syntax,
        "is_one_simple_command",
        autospec=True,
        side_effect=herdr_ownership.shell_syntax.UnsupportedSyntax("parser unavailable"),
    )
    record = store.register(repository, "codex", "session")
    with pytest.raises(store.ScopeError, match="one simple direct Herdr call"):
        herdr_ownership.check(record, "herdr worktree remove --workspace w9")


def test_a_failed_start_does_not_claim_a_later_agent_with_the_same_name(repository: Path, herdr: Path) -> None:
    command = "herdr agent start lane-a --kind claude --pane w9:p1"
    run(repository, command)
    after(repository, command, {"stdout": "Error: failed"})
    set_agents(herdr, "lane-a w9\n")
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == "ask"


@pytest.mark.parametrize("replacement", ["term_replacement session_agent", "term_agent session_replacement"])
def test_an_exited_agents_name_does_not_own_its_replacement(repository: Path, herdr: Path, replacement: str) -> None:
    start_agent(repository, herdr, "w9")
    set_agents(herdr, f"lane-a w9 {replacement}\n")
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == "ask"


@pytest.mark.parametrize("field", ["name", "terminal_id", "pane_id", "workspace_id", "agent_session"])
def test_an_incomplete_start_result_does_not_claim_the_agent(repository: Path, herdr: Path, field: str) -> None:
    command = "herdr agent start lane-a --kind claude --pane w9:p1"
    agent = {
        "name": "lane-a",
        "terminal_id": "term_agent",
        "pane_id": "p1",
        "workspace_id": "w9",
        "agent_session": {"value": "session_agent"},
    }
    del agent[field]
    after(repository, command, {"stdout": json.dumps({"result": {"type": "agent_started", "agent": agent}})})
    set_agents(herdr, "lane-a w9\n")
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == "ask"


@pytest.mark.parametrize("result_type", [None, "workspace_created", "worktree_created"])
def test_a_start_requires_an_agent_started_result(repository: Path, herdr: Path, result_type: str | None) -> None:
    agent = {
        "name": "lane-a",
        "workspace_id": "w9",
        "pane_id": "p1",
        "terminal_id": "term_agent",
        "agent_session": {"value": "session_agent"},
    }
    set_agents(herdr, "lane-a w9 term_agent session_agent\n")
    command = "herdr agent start lane-a --kind claude --pane w9:p1"
    after(repository, command, {"stdout": json.dumps({"result": {"type": result_type, "agent": agent}})})
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == "ask"
