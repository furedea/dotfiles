"""Prefix and regex denials remain distinct from provider approval decisions."""

import json
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
pytestmark = pytest.mark.usefixtures("isolated_project")


@pytest.mark.parametrize(
    "command",
    [
        'cd /tmp/project && node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task review',
        'node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task review; echo done',
        'node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task review | tee /tmp/log',
        'node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task review > /tmp/log',
        'env A=1 node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task review',
        'A=1 node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task review',
        'cd /tmp/project && "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task review',
        'echo ready; timeout 30 node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task review',
    ],
)
def test_companion_requires_one_simple_command(command: str) -> None:
    verdict = guard.decide("forbidden", {"tool_input": {"command": command}})
    assert verdict.decision == "deny"
    assert 'node "<plugin path>/codex-companion.mjs"' in verdict.reason
    assert "--cwd <dir> instead of cd" in verdict.reason
    assert "no pipes, redirects, &&, or assignments" in verdict.reason
    assert "sandbox exclusion matches only that form" in verdict.reason


@pytest.mark.parametrize(
    "command",
    [
        'node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task "review $HOME"',
        'node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task $TASK',
        'node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --focus "review `pwd`"',
        'node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task "review $(pwd)"',
    ],
)
def test_companion_rejects_expansions_outside_single_quotes(command: str) -> None:
    verdict = guard.decide("forbidden", {"tool_input": {"command": command}})
    assert verdict.decision == "deny"
    assert "task or focus text must not contain a dollar sign or backtick" in verdict.reason
    assert "sandbox exclusion does not match a command with expansions" in verdict.reason


def test_companion_is_denied_when_its_simple_command_shape_cannot_be_parsed(mocker: MockerFixture) -> None:
    mocker.patch.object(
        guard.shell_syntax,
        "is_one_simple_command",
        autospec=True,
        side_effect=guard.shell_syntax.UnsupportedSyntax("parser unavailable"),
    )
    command = 'node "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --cwd /tmp/project --task "確認"'
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "deny"


@pytest.mark.parametrize("kind", ["allowed", "forbidden"])
@pytest.mark.parametrize(
    "command",
    [
        f'node "{Path.home()}/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --task review',
        f'node "{Path.home()}/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --cwd /tmp/project --task "日本語のタスクを確認"',
        f"node \"{Path.home()}/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs\" --task 'review $HOME'",
        f'node "{Path.home()}/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" --cwd /tmp/project --task "引用符と && | > は本文" --background',
        'echo "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" | tee /tmp/log',
        'node "/plugin path/other.mjs" > /tmp/log',
    ],
)
def test_simple_companion_calls_and_unrelated_commands_stay_allowed(kind: str, command: str) -> None:
    assert guard.decide(kind, {"tool_input": {"command": command}}).decision == "allow"


@pytest.mark.parametrize("quote", ['"', "'"])
def test_companion_rejects_quoted_literal_tilde_paths(quote: str) -> None:
    script = "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs"
    command = f"node {quote}{script}{quote} task --cwd /tmp/project review"
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "deny"


@pytest.mark.parametrize("quote", ['"', "'"])
@pytest.mark.parametrize("version", ["0.0.0", "1.0.3", "12.345.6789"])
def test_companion_accepts_numeric_versions_in_the_plugin_cache(quote: str, version: str) -> None:
    script = f"{Path.home()}/.claude/plugins/cache/openai-codex/codex/{version}/scripts/codex-companion.mjs"
    command = f'node {quote}{script}{quote} task --cwd /tmp/project "review"'
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "allow"


def test_companion_uses_the_current_home_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "home.with[pattern]"
    monkeypatch.setenv("HOME", str(home))
    script = f"{home}/.claude/plugins/cache/openai-codex/codex/1.2.3/scripts/codex-companion.mjs"
    command = f'node "{script}" task "review"'
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "allow"
    other_home = str(home).replace("home.with[pattern]", "homeXwithp")
    command = command.replace(str(home), other_home)
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "deny"


@pytest.mark.parametrize("root", ["~", str(Path.home())])
@pytest.mark.parametrize(
    "suffix",
    [
        "../1.0.3/scripts/codex-companion.mjs",
        "1.0.3/../1.0.3/scripts/codex-companion.mjs",
        "1.0.3/scripts/../../codex-companion.mjs",
        "1.0.3/other/codex-companion.mjs",
        "1.0.3/scripts/other.mjs",
        "1.0.3/scripts/nested/codex-companion.mjs",
        "v1.0.3/scripts/codex-companion.mjs",
        "1.0.3-beta/scripts/codex-companion.mjs",
        "1.0/scripts/codex-companion.mjs",
        "1.0.3.4/scripts/codex-companion.mjs",
        "1x0x3/scripts/codex-companion.mjs",
        "\uff11.\uff10.\uff13/scripts/codex-companion.mjs",
        "*/scripts/codex-companion.mjs",
        "1.0.3//scripts/codex-companion.mjs",
        "1.0.3/scripts/./codex-companion.mjs",
        "1.0.3/scripts/codex-companion.mjs/",
    ],
)
def test_companion_rejects_paths_outside_the_exact_versioned_script(root: str, suffix: str) -> None:
    command = f'node "{root}/.claude/plugins/cache/openai-codex/codex/{suffix}" task "review"'
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "deny"


@pytest.mark.parametrize(
    "command",
    [
        'node "/tmp/codex-companion.mjs" task "review"',
        'node "~/.claude/plugins/cache/other/codex/1.0.3/scripts/codex-companion.mjs" task "review"',
        'node --require /tmp/inject.js "~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs"',
        '"~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs" task "review"',
    ],
)
def test_companion_requires_node_followed_by_the_real_plugin_script(command: str) -> None:
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "deny"


@pytest.mark.parametrize(
    "command,status,reason",
    [
        ("git status", 0, ""),
        ("rm codex/hooks.json", 2, "Do not delete files"),
        ("git rm codex/hooks.json", 2, "Do not remove tracked files"),
        ("git status && rm codex/hooks.json", 2, "rm codex/hooks.json"),
        ("bash -c 'echo hello'", 2, "Do not hide shell commands"),
    ],
)
def test_generated_deny_prefixes(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    status: int,
    reason: str,
) -> None:
    policy = tmp_path / "permissions.json"
    policy.write_text(
        json.dumps(
            {
                "version": 1,
                "rules": [
                    {"decision": "deny", "prefix": ["rm"], "justification": "Do not delete files"},
                    {"decision": "deny", "prefix": ["git", "rm"], "justification": "Do not remove tracked files"},
                    {"decision": "deny", "prefix": ["bash", "-c"], "justification": "Do not hide shell commands"},
                ],
            }
        )
    )
    rules = tmp_path / "rules.json"
    rules.write_text(
        json.dumps(
            {"version": 1, "rules": [{"patterns": ["^never-match-this-command$"], "justification": "Test rule"}]}
        )
    )
    monkeypatch.setenv("AGENT_COMMAND_PERMISSIONS", str(policy))
    monkeypatch.setenv("AGENT_FORBIDDEN_COMMAND_RULES", str(rules))
    assert guard.check("forbidden", {"tool_input": {"command": command}}) == status
    output = capsys.readouterr().err
    if status:
        assert "forbidden command" in output
        assert reason in output
    else:
        assert output == ""


@pytest.mark.parametrize(
    "command",
    [
        ".venv/bin/python -c 'print(1)'",
        "./.venv/bin/python3 scripts/check_project.py",
        "/tmp/project/.venv/bin/python -m pytest",
        "git add .",
        "git add -A",
        "git add --all",
        "ls && git add .",
        "echo ok | xargs -I {} git add -A",
        "git   add   .",
        "git add --all --verbose",
        "git commit --no-verify -m example",
        "git commit -m test --no-verify",
        "git commit -n -m test",
        "git   commit   --no-verify",
        "git -c core.fsmonitor=false add -A",
        "git -c core.fsmonitor=false commit --no-verify -m x",
        "git -C /tmp/project add .",
        "/usr/bin/git add -A",
        "env GIT_PAGER=cat git add --all",
        "timeout 30 git commit -n -m test",
        "find . -name '*.pyc' -delete",
        "find . -type f -exec rm {} +",
        "find . -name x -execdir rm {} +",
        "python3 -m pip install requests",
        "python -m pip install requests",
        "python3 -I -m ensurepip",
        "uv run --frozen python -m pip install requests",
        "herdr agent start lane-a --kind claude --pane w1:p2 -- --dangerously-skip-permissions",
        "herdr agent start lane-a --kind codex --pane w1:p2 -- --sandbox danger-full-access",
        "herdr agent start lane-a --kind codex --pane w1:p2 -- --model sonnet --effort medium",
        "herdr agent start lane-a --kind claude --pane w1:p2 -- --model sonnet --effort medium --settings x.json",
        "herdr agent start lane-a --kind claude --pane w1:p2 -- --model sonnet --effort high",
        "herdr agent start lane-a --kind claude --pane w1:p2 -- --effort medium --model sonnet",
        "herdr agent start lane-a --kind claude --pane w1:p2 -- --model opus --effort high",
        "herdr agent start lane-a --kind codex --pane w1:p2 -- --model opus --effort medium",
    ],
)
def test_global_rules_reject_policy_bypasses(command: str) -> None:
    assert guard.check("forbidden", {"tool_input": {"command": command}}) == 2


@pytest.mark.parametrize("model", ["sonnet", "opus"])
def test_lanes_may_start_on_sonnet_or_opus_at_medium_effort(model: str) -> None:
    command = f"herdr agent start lane-a --kind claude --pane w1:p2 -- --model {model} --effort medium"
    assert guard.check("forbidden", {"tool_input": {"command": command}}) == 0


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /tmp/example",
        "rm -r build",
        "cargo install ripgrep",
        "npm install -g typescript",
        "uv tool install ruff",
        "uv add --dev pytest",
        "nix profile install nixpkgs#ripgrep",
        "security find-generic-password -s example -w",
        "launchctl bootout gui/501/org.example.agent",
        "gh repo delete owner/repo",
        "gh auth login",
        "mosh example.internal",
        "killall Dock",
    ],
)
def test_global_prefixes_deny_irreversible_or_credential_operations(command: str) -> None:
    assert guard.check("forbidden", {"tool_input": {"command": command}}) == 2


@pytest.mark.parametrize(
    "command",
    ["rm scratch.txt", "git rm agents/old.py", "git worktree remove ../topic", "git stash drop", "find . -name x"],
)
def test_reversible_or_asked_operations_are_not_forbidden(command: str) -> None:
    assert guard.check("forbidden", {"tool_input": {"command": command}}) == 0


def test_global_prefix_rejects_home_manager_activation(capsys: pytest.CaptureFixture[str]) -> None:
    assert guard.check("forbidden", {"tool_input": {"command": "home-manager switch --flake ./#kaito"}}) == 2
    assert "Do not activate Home Manager configurations" in capsys.readouterr().err


@pytest.mark.parametrize("kind", ["allowed", "forbidden"])
@pytest.mark.parametrize(
    "command",
    [
        "bash <<EOF\necho $X\nEOF",
        "echo $'\\x41'",
        "f(){ git add -A; }",
        "f() { git commit --no-verify -m x; }; f",
        "function f { bash -c 'echo hi'; }",
    ],
)
def test_uninspectable_commands_are_left_to_the_user(kind: str, command: str) -> None:
    verdict = guard.decide(kind, {"tool_input": {"command": command}})
    assert verdict.decision == "ask"
    assert "review" in verdict.reason


@pytest.mark.parametrize(
    "command",
    [
        'echo "$(rm -rf build)"',
        'for d in a b; do rm -rf "$d"; done',
        "bash <<'EOF'\nrm -rf build\nEOF",
        "if true; then git add -A; fi",
        'echo "${TARGET:-$(rm -rf build)}"',
        "{ rm -rf /Users/kaito/project/build; } > $'out'",
        '( rm -rf build ) >> "$LOG"',
    ],
)
def test_denials_apply_to_commands_inside_substitutions_clauses_and_shell_heredocs(command: str) -> None:
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "deny"


def test_heredoc_bodies_are_data_not_commands() -> None:
    command = "python3 - <<'EOF'\nprint('git add -A && git commit --no-verify')\nEOF"
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "allow"


def test_literal_deny_prefixes_win_over_run_time_arguments() -> None:
    verdict = guard.decide("forbidden", {"tool_input": {"command": "rm -rf $TARGET"}})
    assert verdict.decision == "deny"
    assert "directory trees" in verdict.reason


@pytest.mark.parametrize("command", ["git push $FLAGS origin topic", "cd $DIR", "$CMD --help", "ls *.md"])
def test_run_time_arguments_are_the_allowed_kinds_concern(command: str) -> None:
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "allow"


def test_denials_keep_their_exit_status_and_escalations_report_an_ask_decision(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert guard.check("forbidden", {"tool_input": {"command": "rm -rf build"}}) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "forbidden command" in captured.err
    assert guard.check("forbidden", {"tool_input": {"command": "echo $'date'"}}) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    decision = json.loads(captured.out)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "ask"
    assert "review" in decision["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        'gh pr create --title fix --body "Do not use git add -A here"',
        'git commit -m "explain --no-verify policy"',
        "echo 'never run find . -delete here'",
    ],
)
def test_prose_arguments_do_not_trigger_forbidden_patterns(command: str) -> None:
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "allow"


@pytest.mark.parametrize(
    "command",
    [
        "git add -A",
        "xargs git add -A",
        "env GIT_PAGER=cat git add -A",
        "timeout 30 git add -A",
        "bash -c 'git add -A'",
        "xargs sh -c 'git commit --no-verify -m x'",
        'eval "git add -A"',
        'echo "$(git add -A)"',
    ],
)
def test_forbidden_patterns_still_reach_commands_that_run(command: str) -> None:
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "deny"


def test_inline_pr_bodies_that_mention_forbidden_commands_pass() -> None:
    command = "gh pr create --head topic --body \"$(cat <<'EOF'\nNever run git add -A or --no-verify.\nEOF\n)\""
    assert guard.decide("forbidden", {"tool_input": {"command": command}}).decision == "allow"


@pytest.mark.parametrize(
    "payload,writer,session",
    [
        ({"tool_input": {"command": "rm -rf build"}, "session_id": "s1"}, "blocked", "s1"),
        ({"tool_input": {"command": "echo $'date'"}, "session_id": "s2"}, "escalated", "s2"),
        (["not", "an", "object"], "blocked", ""),
    ],
)
def test_denials_and_escalations_are_recorded_with_their_session(
    *, mocker: MockerFixture, payload: object, writer: str, session: str
) -> None:
    recorders = {name: mocker.patch.object(guard.audit_log, name) for name in ("blocked", "escalated")}
    verdict = guard.decide("forbidden", payload)
    recorders[writer].assert_called_once_with(
        guard.audit_log.Refusal(
            "Bash",
            "guard_forbidden_commands.sh",
            session,
            payload=payload if isinstance(payload, dict) else None,
            detail=verdict.detail,
        )
    )
    assert all(not recorder.called for name, recorder in recorders.items() if name != writer)


def test_allowed_commands_are_not_recorded(mocker: MockerFixture) -> None:
    recorders = [mocker.patch.object(guard.audit_log, name) for name in ("blocked", "escalated")]
    assert guard.decide("forbidden", {"tool_input": {"command": "git status"}}).decision == "allow"
    assert all(not recorder.called for recorder in recorders)


def test_a_configuration_failure_is_recorded_without_the_command(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    blocked = mocker.patch.object(guard.audit_log, "blocked")
    monkeypatch.setenv("AGENT_FORBIDDEN_COMMAND_RULES", str(tmp_path / "missing.json"))
    payload = {"tool_input": {"command": "rm -rf build"}, "session_id": "s3"}
    verdict = guard.decide("forbidden", payload)
    assert verdict.decision == "deny"
    blocked.assert_called_once_with(
        guard.audit_log.Refusal("Bash", "guard_forbidden_commands.sh", "s3", payload=payload, detail=verdict.detail)
    )
