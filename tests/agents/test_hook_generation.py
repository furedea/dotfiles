"""Provider settings preserve the native hook contracts after rendering."""

import json
from pathlib import Path

import pytest

from tests.runtime import CliRunner


pytestmark = pytest.mark.integration


def test_generated_claude_lint_hook_uses_the_dispatcher_without_if(agent_harness: CliRunner, tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    agent_harness("generate-claude-settings", "--output", str(path))
    settings = json.loads(path.read_text())
    groups = [group for group in settings["hooks"]["PostToolUse"] if group.get("matcher") == "Write|Edit"]
    lint_hooks = [hook for group in groups for hook in group["hooks"] if "lint_format.py" in hook["command"]]
    assert len(lint_hooks) == 1
    assert lint_hooks[0]["command"].endswith('lint_format.py"')
    assert "if" not in lint_hooks[0]


def test_generated_codex_lint_hook_matches_native_apply_patch_aliases(
    agent_harness: CliRunner, tmp_path: Path
) -> None:
    path = tmp_path / "hooks.json"
    agent_harness("generate-codex-hooks", "--output", str(path))
    hooks = json.loads(path.read_text())["hooks"]["PostToolUse"]
    groups = [group for group in hooks if group.get("matcher") == "^apply_patch$|^Edit$|^Write$"]
    lint_hooks = [hook for group in groups for hook in group["hooks"] if 'hook_adapter.py" lint' in hook["command"]]
    assert len(lint_hooks) == 1
