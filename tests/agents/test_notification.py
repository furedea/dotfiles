"""Native provider notifications replace local notification hooks."""

import json
import tomllib

from tests.runtime import REPO_ROOT


def test_claude_uses_the_native_automatic_notification_channel() -> None:
    settings = json.loads((REPO_ROOT / "agents/claude/settings.base.json").read_text())
    assert settings["preferredNotifChannel"] == "auto"


def test_codex_notifies_for_completion_and_approval_only_while_unfocused() -> None:
    config = tomllib.loads((REPO_ROOT / "agents/codex/config.toml").read_text())["tui"]
    assert set(config["notifications"]) == {"agent-turn-complete", "approval-requested"}
    assert config["notification_condition"] == "unfocused"
    assert config["notification_method"] == "auto"


def test_provider_hooks_do_not_register_local_macos_notifications() -> None:
    source = (REPO_ROOT / "agents/hooks.json").read_text()
    assert "notify_macos_" not in source
    assert not {"Notification", "SubagentStop"} & json.loads(source)["claude"].keys()


def test_verification_is_the_only_claude_stop_hook() -> None:
    hooks = json.loads((REPO_ROOT / "agents/hooks.json").read_text())
    commands = [hook["command"] for group in hooks["claude"]["Stop"] for hook in group["hooks"]]
    assert commands == ['"$HOME/.claude/hooks/verification_session.py" claude stop']
