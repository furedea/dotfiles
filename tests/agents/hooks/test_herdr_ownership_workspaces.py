"""Workspace ownership follows recorded workspace and terminal instances."""

import json
from pathlib import Path

import pytest

from tests.runtime import REPO_ROOT
from tests.agents.hooks.herdr_runtime import (
    CLOSE,
    CREATE,
    PRIMARY,
    TERMINAL,
    after,
    created,
    decision,
    open_primary,
    open_lane,
    run,
    set_agents,
    set_terminals,
    start_agent,
    workspace_list,
)


import session_store as store


@pytest.mark.parametrize("command", ["herdr workspace close w9", "herdr worktree remove --workspace w9"])
def test_starting_a_lane_in_the_users_workspace_does_not_own_it(repository: Path, herdr: Path, command: str) -> None:
    start_agent(repository, herdr, "w9")
    set_agents(herdr, "lane-a w9\n")
    assert decision(run(repository, command)) == "ask"


@pytest.mark.parametrize(
    "command",
    [f"{CLOSE} --group", "herdr workspace close --group w5", "herdr workspace close w5 --group --force"],
)
def test_a_group_close_always_asks(repository: Path, herdr: Path, tmp_path: Path, command: str) -> None:
    open_primary(repository, tmp_path)
    assert decision(run(repository, command)) == "ask"


@pytest.mark.parametrize(
    "command",
    [
        f"HERDR_SOCKET_PATH=/tmp/other.sock {CLOSE}",
        f"X=1 {CLOSE}",
        f"env HERDR_SOCKET_PATH=/tmp/other.sock {CLOSE}",
        f"env {CLOSE}",
        f"command {CLOSE}",
        f"sh -c '{CLOSE}'",
        f"/usr/local/bin/{CLOSE}",
        f"{CLOSE} --session other",
        f"{CLOSE} --session=other",
        f"{CLOSE} --socket /tmp/other.sock",
        f"{CLOSE} --socket-path=/tmp/other.sock",
        f"{CLOSE}; echo done",
        f"true && {CLOSE}",
        f"({CLOSE})",
        f"{{ {CLOSE}; }}",
        f"{CLOSE} | cat",
        f"{CLOSE} > /dev/null",
        f"{CLOSE} < /dev/null",
    ],
)
def test_a_close_that_is_not_one_plain_call_asks(repository: Path, herdr: Path, tmp_path: Path, command: str) -> None:
    open_primary(repository, tmp_path)
    assert decision(run(repository, command)) == "ask"
    assert decision(run(repository, CLOSE)) == "allow"


def test_closing_a_primary_the_user_already_had_asks(repository: Path, herdr: Path, tmp_path: Path) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    assert decision(run(repository, CLOSE)) == "ask"


@pytest.mark.parametrize(
    "response", [{"stdout": "Error: failed"}, {"stdout": created(), "interrupted": True}, "", None]
)
def test_a_failed_create_owns_nothing(repository: Path, herdr: Path, tmp_path: Path, response: object) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, CREATE)
    after(repository, CREATE, response)
    assert decision(run(repository, CLOSE)) == "ask"


@pytest.mark.parametrize(
    "command",
    [
        f"{CREATE}; echo done",
        f"{CREATE} | cat",
        f"{CREATE} > /dev/null",
        f"echo '{created()}' && {CREATE}",
        f"env {CREATE}",
        f"sh -c '{CREATE}'",
        f"X=1 {CREATE}",
    ],
    ids=[
        "a list",
        "a pipe",
        "a redirect",
        "a printed result",
        "an env wrapper",
        "a shell wrapper",
        "an assignment",
    ],
)
def test_a_create_that_is_not_one_plain_call_owns_nothing(
    repository: Path, herdr: Path, tmp_path: Path, command: str
) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, command)
    after(repository, command, {"stdout": created()})
    assert decision(run(repository, CLOSE)) == "ask"


def test_a_record_from_another_session_is_not_honored(repository: Path, herdr: Path, tmp_path: Path) -> None:
    store.register(repository, "codex", "other")
    open_primary(repository, tmp_path)
    assert decision(run(repository, CLOSE, session="other")) == "ask"


def test_a_primary_workspace_from_another_session_post_step_is_not_recorded_here(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    store.register(repository, "codex", "other")
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    after(repository, CREATE, {"stdout": created()}, session="other")
    assert decision(run(repository, CLOSE)) == "ask"


@pytest.mark.parametrize("terminals", [("term_other",), ()], ids=["another terminal", "no pane"])
def test_the_same_id_label_and_path_with_another_root_terminal_asks(
    repository: Path, herdr: Path, tmp_path: Path, terminals: tuple[str, ...]
) -> None:
    """A reused workspace ID or a restarted server never repeats the terminal instance."""
    open_primary(repository, tmp_path)
    set_terminals(tmp_path, *terminals)
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    assert decision(run(repository, CLOSE)) == "ask"


def test_the_recorded_terminal_may_sit_among_other_panes(repository: Path, herdr: Path, tmp_path: Path) -> None:
    open_primary(repository, tmp_path)
    set_terminals(tmp_path, "term_extra", TERMINAL)
    assert decision(run(repository, CLOSE)) == "allow"


@pytest.mark.parametrize("pane", [{"pane_id": "p1", "cwd": PRIMARY}, {"pane_id": "p1", "terminal_id": ""}])
def test_a_result_without_a_root_terminal_is_not_owned(
    repository: Path, herdr: Path, tmp_path: Path, pane: dict
) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, CREATE)
    result = {
        "type": "workspace_created",
        "workspace": {"workspace_id": "w5", "label": "site"},
        "root_pane": {**pane, "cwd": PRIMARY},
    }
    after(repository, CREATE, {"stdout": json.dumps({"result": result})})
    assert decision(run(repository, CLOSE)) == "ask"


@pytest.mark.parametrize(("path", "label"), [("/repos/other", "site"), (PRIMARY, "renamed")])
def test_a_reused_id_with_another_path_or_label_asks(
    repository: Path, herdr: Path, tmp_path: Path, path: str, label: str
) -> None:
    open_primary(repository, tmp_path)
    workspace_list(tmp_path, ("w5", path, label))
    assert decision(run(repository, CLOSE)) == "ask"


def test_a_workspace_the_result_does_not_name_is_not_claimed(repository: Path, herdr: Path, tmp_path: Path) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"), ("w9", PRIMARY, "site"))
    run(repository, CREATE)
    after(repository, CREATE, {"stdout": created("w5")})
    assert decision(run(repository, "herdr workspace close w9")) == "ask"


def test_a_result_without_a_root_pane_directory_is_not_owned(repository: Path, herdr: Path, tmp_path: Path) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, CREATE)
    result = {
        "type": "workspace_created",
        "workspace": {"workspace_id": "w5", "label": "site"},
        "root_pane": {"pane_id": "p1"},
    }
    after(repository, CREATE, {"stdout": json.dumps({"result": result})})
    assert decision(run(repository, CLOSE)) == "ask"


def test_a_created_label_that_differs_from_the_asked_one_is_not_owned(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    run(repository, CREATE)
    after(repository, CREATE, {"stdout": created(label="other")})
    assert decision(run(repository, CLOSE)) == "ask"


@pytest.mark.parametrize("close", ["herdr workspace close w6", "herdr worktree remove --workspace w6"])
def test_created_workspaces_and_agents_follow_one_ownership_flow(
    repository: Path, herdr: Path, tmp_path: Path, close: str
) -> None:
    open_primary(repository, tmp_path)
    open_lane(repository, tmp_path)
    start_agent(repository, herdr, "w6")
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == "allow"
    assert decision(run(repository, close)) == "allow"
    after(
        repository,
        close,
        {
            "stdout": json.dumps(
                {"result": {"type": "ok"}}
                if "workspace close" in close
                else {"result": {"type": "worktree_removed", "workspace_id": "w6"}}
            )
        },
    )
    assert decision(run(repository, close)) == "ask"
    set_agents(herdr, "")
    assert decision(run(repository, CLOSE)) == "allow"
    after(repository, CLOSE, {"stdout": json.dumps({"result": {"type": "ok"}})})
    assert decision(run(repository, CLOSE)) == "ask"


@pytest.mark.parametrize(
    "command",
    [
        CREATE,
        "herdr worktree create --workspace w5 --branch feat/x",
        "herdr agent start lane-a --kind claude --pane w5:p1",
    ],
)
@pytest.mark.parametrize(
    "form",
    [
        "{}; echo done",
        "{} > /tmp/result",
        "HERDR_SOCKET_PATH=/tmp/other {}",
        "env {}",
        "herdr --session other {}",
        "{} --session other",
    ],
)
def test_only_a_single_direct_create_or_start_records_ownership(
    repository: Path, herdr: Path, tmp_path: Path, command: str, form: str
) -> None:
    response = json.loads(created())
    response["result"]["worktree"] = {"path": PRIMARY}
    response["result"]["type"] = {
        "workspace": "workspace_created",
        "worktree": "worktree_created",
        "agent": "agent_started",
    }[command.split()[1]]
    response["result"]["agent"] = {
        "name": "lane-a",
        "workspace_id": "w5",
        "pane_id": "p1",
        "terminal_id": "term_agent",
        "agent_session": {"value": "session_agent"},
    }
    wrapped = form.format(command.removeprefix("herdr ") if form.startswith("herdr ") else command)
    after(repository, wrapped, {"stdout": json.dumps(response)})
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    set_agents(herdr, "lane-a w5\n")
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == "ask"
    assert decision(run(repository, CLOSE)) == "ask"


@pytest.mark.parametrize("command", ["herdr workspace close w6", "herdr worktree remove --workspace w6"])
@pytest.mark.parametrize(
    "agent", ["reviewer w6 term_other\n", "lane-a w6 term_reused\n", "lane-a w6 term_agent session_replacement\n"]
)
def test_a_created_workspace_with_an_unowned_agent_asks(
    repository: Path, herdr: Path, tmp_path: Path, command: str, agent: str
) -> None:
    open_primary(repository, tmp_path)
    open_lane(repository, tmp_path)
    start_agent(repository, herdr, "w6")
    set_agents(herdr, agent)
    assert decision(run(repository, command)) == "ask"


def test_a_created_workspace_can_close_with_its_recorded_agent(repository: Path, herdr: Path, tmp_path: Path) -> None:
    open_primary(repository, tmp_path)
    start_agent(repository, herdr, "w5")
    assert decision(run(repository, CLOSE)) == "allow"
    after(repository, CLOSE, {"stdout": json.dumps({"result": {"type": "ok"}})})
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == "ask"


@pytest.mark.parametrize("workspace", ["w6", None])
def test_worktree_removal_expires_only_the_workspace_named_in_the_result(
    repository: Path, herdr: Path, tmp_path: Path, workspace: str | None
) -> None:
    open_primary(repository, tmp_path)
    open_lane(repository, tmp_path)
    start_agent(repository, herdr, "w6")
    result = {"type": "worktree_removed"}
    if workspace is not None:
        result["workspace_id"] = workspace
    after(repository, "herdr worktree remove --workspace lane", {"stdout": json.dumps({"result": result})})
    expected = "ask" if workspace == "w6" else "allow"
    assert decision(run(repository, "herdr workspace close w6")) == expected
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == expected
    assert decision(run(repository, CLOSE)) == "allow"


def test_a_workspace_without_an_attached_worktree_matches_its_root_directory(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    open_primary(repository, tmp_path)
    row = {"workspace_id": "w5", "label": "site", "root_pane": {"cwd": PRIMARY}}
    (tmp_path / "workspaces.json").write_text(json.dumps({"result": {"workspaces": [row]}}))
    assert decision(run(repository, CLOSE)) == "allow"


def test_ownership_hooks_cover_creation_and_cleanup_results() -> None:
    settings = json.loads((REPO_ROOT / "agents/hooks.json").read_text())
    hooks = [
        hook
        for group in settings["claude"]["PostToolUse"]
        for hook in group["hooks"]
        if "verification_session.py" in hook["command"]
    ]
    assert {hook["if"] for hook in hooks} == {
        "Bash(herdr workspace create *)",
        "Bash(herdr worktree create *)",
        "Bash(herdr agent start *)",
        "Bash(herdr workspace close *)",
        "Bash(herdr worktree remove *)",
    }
    groups = settings["codex"]["hooks"]["PostToolUse"]
    assert any(
        "exec_command" in group["matcher"]
        and any("verification_session.py" in hook["command"] for hook in group["hooks"])
        for group in groups
    )


def test_removing_a_workspace_group_asks(repository: Path, herdr: Path, tmp_path: Path) -> None:
    open_primary(repository, tmp_path)
    assert decision(run(repository, "herdr worktree remove --workspace w5 --group")) == "ask"


@pytest.mark.parametrize("command", [CLOSE, "herdr workspace close w6", "herdr worktree remove --workspace w6"])
def test_failed_cleanup_preserves_prompts_and_retries_until_success(
    repository: Path, herdr: Path, tmp_path: Path, command: str
) -> None:
    open_primary(repository, tmp_path)
    open_lane(repository, tmp_path)
    workspace = "w5" if command == CLOSE else "w6"
    start_agent(repository, herdr, workspace)
    assert decision(run(repository, command)) == "allow"
    after(repository, command, {"stdout": json.dumps({"error": {"code": "workspace_group_close_required"}})})
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == "allow"
    assert decision(run(repository, command)) == "allow"
    result = (
        {"type": "ok"} if "workspace close" in command else {"type": "worktree_removed", "workspace_id": workspace}
    )
    after(repository, command, {"stdout": json.dumps({"result": result})})
    assert decision(run(repository, "herdr agent prompt lane-a hello")) == "ask"
    assert decision(run(repository, command)) == "ask"
    assert decision(run(repository, CLOSE)) == ("ask" if command == CLOSE else "allow")


def test_the_primary_cannot_be_removed_as_a_worktree(repository: Path, herdr: Path, tmp_path: Path) -> None:
    open_primary(repository, tmp_path)
    assert decision(run(repository, "herdr worktree remove --workspace w5")) == "ask"


@pytest.mark.parametrize("extra", ["--force", "--group", "extra", "--workspace w6"])
def test_worktree_removal_with_extra_words_asks(repository: Path, herdr: Path, tmp_path: Path, extra: str) -> None:
    open_lane(repository, tmp_path)
    assert decision(run(repository, f"herdr worktree remove --workspace w6 {extra}")) == "ask"
    assert decision(run(repository, "herdr worktree remove --workspace w6")) == "allow"


@pytest.mark.parametrize("action", ["workspace", "worktree"])
@pytest.mark.parametrize("result_type", [None, "agent_started", "workspace_created", "worktree_created"])
def test_creation_requires_the_matching_result_type(
    repository: Path, herdr: Path, tmp_path: Path, action: str, result_type: str | None
) -> None:
    command = CREATE if action == "workspace" else "herdr worktree create --workspace w9 --branch feat/x"
    response = json.loads(created())
    response["result"]["type"] = result_type
    response["result"]["worktree"] = {"path": PRIMARY}
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    after(repository, command, {"stdout": json.dumps(response)})
    expected = "allow" if result_type == f"{action}_created" else "ask"
    assert decision(run(repository, CLOSE)) == expected


def test_a_lane_created_in_the_users_primary_does_not_own_the_primary(
    repository: Path, herdr: Path, tmp_path: Path
) -> None:
    workspace_list(tmp_path, ("w5", PRIMARY, "site"))
    open_lane(repository, tmp_path)
    command = "herdr workspace close w6"
    assert decision(run(repository, command)) == "allow"
    after(repository, command, {"stdout": json.dumps({"result": {"type": "ok"}})})
    assert decision(run(repository, CLOSE)) == "ask"
