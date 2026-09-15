"""Herdr command configuration works independently of the server's PATH."""

from pathlib import Path
import shlex
import sys
import tomllib

import pytest

from conftest import REPO_ROOT


CONFIG = tomllib.loads((REPO_ROOT / "herdr/config.toml").read_text())


def command_for(description: str) -> dict:
    matches = [item for item in CONFIG["keys"]["command"] if item["description"] == description]
    assert len(matches) == 1, description
    return matches[0]


def test_herdr_uses_a_fixed_dark_catppuccin_theme() -> None:
    assert CONFIG["theme"]["name"] == "catppuccin"
    assert CONFIG["theme"]["auto_switch"] is False


def test_agent_rows_show_semantic_state_text() -> None:
    assert any("state_text" in row for row in CONFIG["ui"]["sidebar"]["agents"]["rows"])


def test_popup_tool_paths_do_not_depend_on_server_path() -> None:
    yazi = shlex.split(command_for("run yazi")["command"])
    assert yazi[0] == "/usr/bin/env"
    assert Path(yazi[-1]).is_absolute() and Path(yazi[-1]).name == "yazi"
    lazygit = shlex.split(command_for("run lazygit")["command"])
    assert len(lazygit) == 1
    assert Path(lazygit[0]).is_absolute() and Path(lazygit[0]).name == "lazygit"


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "darwin", reason="requires the installed macOS Home Manager profile")
def test_popup_tool_paths_exist_in_the_installed_profile() -> None:
    yazi = shlex.split(command_for("run yazi")["command"])
    lazygit = shlex.split(command_for("run lazygit")["command"])
    for name in (yazi[0], yazi[-1], lazygit[0]):
        assert Path(name).is_file(), name


def test_yazi_popup_uses_nix_neovim_for_both_editor_variables() -> None:
    assert shlex.split(command_for("run yazi")["command"]) == [
        "/usr/bin/env",
        "EDITOR=/etc/profiles/per-user/kaito/bin/nvim",
        "VISUAL=/etc/profiles/per-user/kaito/bin/nvim",
        "/etc/profiles/per-user/kaito/bin/yazi",
    ]


def test_terminal_browser_opens_in_a_right_split_from_the_active_pane() -> None:
    browser = command_for("open terminal browser")
    assert browser["key"] == "prefix+ctrl+e"
    assert browser["type"] == "shell"
    assert shlex.split(browser["command"]) == [
        "HERDR_PANE_ID=$HERDR_ACTIVE_PANE_ID",
        "HERDR_TAB_ID=$HERDR_ACTIVE_TAB_ID",
        "/etc/profiles/per-user/kaito/bin/terminal-browser",
        "--split",
        "right",
    ]


def test_reviewr_starts_with_branch_changes() -> None:
    config = tomllib.loads((REPO_ROOT / "herdr/reviewr.toml").read_text())
    assert config["default_scope"] == "branch"


def test_pull_request_merge_uses_the_standard_popup_and_managed_helper() -> None:
    command = command_for("squash-merge current PR")
    assert command["key"] == "prefix+ctrl+p"
    assert command["type"] == "popup"
    assert command["width"] == command["height"] == "85%"
    assert ".local/libexec/herdr_merge_pull_request.sh" in command["command"]
    assert "gh pr merge" not in command["command"]
