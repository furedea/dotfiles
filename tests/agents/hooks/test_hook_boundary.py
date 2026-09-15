"""Pure hook decisions and provider translations are independently observable."""

import io
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from tests.runtime import REPO_ROOT, load_script_module

hook_translation = load_script_module("agents/codex/hooks/hook_translation.py", "codex_hook_translation")
files = load_script_module("agents/hooks/guard_file.py", "guard_file")
audit = load_script_module("agents/hooks/audit_log.py", "audit_log")


def test_patch_paths_include_moves_and_deletions_once() -> None:
    patch = "*** Add File: a.py\n*** Update File: a.py\n*** Delete File: old.py\n*** Move to: new.py"
    assert hook_translation.patch_input.paths(patch) == ("a.py", "new.py", "old.py")


def test_scanner_receives_only_added_lines() -> None:
    assert hook_translation.patch_input.added_text("--- old\n+++ new\n context\n-old\n+new\n+more") == "new\nmore"


@pytest.mark.parametrize(
    "suffix,kind",
    [
        (".py", "py"),
        (".sh", "sh"),
        (".js", "js"),
        (".ts", "js"),
        (".jsx", "js"),
        (".tsx", "js"),
        (".rs", "rs"),
        (".nix", "nix"),
        (".md", "md"),
        (".markdown", "md"),
        (".json", "json_toml"),
        (".toml", "json_toml"),
        (".yaml", "gha"),
        (".yml", "gha"),
        (".txt", "txt"),
        (".lua", "lua"),
        (".tex", "tex"),
        (".bib", "tex"),
        (".cls", "tex"),
        (".sty", "tex"),
    ],
)
def test_formatter_routes_supported_extensions(suffix: str, kind: str) -> None:
    assert hook_translation.EXTENSIONS[Path("file" + suffix).suffix] == kind


def test_translated_command_preserves_session_without_extra_tool_fields() -> None:
    assert hook_translation.translated(
        {"session_id": "s", "untrusted": "ignored"}, "Bash", {"command": "git status"}
    ) == {
        "tool_name": "Bash",
        "tool_input": {"command": "git status"},
        "session_id": "s",
    }


def test_staged_filename_policy_does_not_guess_from_generic_secret_words(tmp_path: Path) -> None:
    policy = REPO_ROOT / "agents/hooks/rules/secret_commit_policy.json"
    rules = files.commit_filename_rules(policy)
    assert any(files.regex_matches(rule["pattern"], ".env.local", True) for rule in rules)
    assert not any(files.regex_matches(rule["pattern"], "test_secret_policy.py", True) for rule in rules)


def test_failed_staged_file_enumeration_is_not_an_empty_success(mocker: MockerFixture) -> None:
    mocker.patch.object(files.subprocess, "run", side_effect=files.subprocess.CalledProcessError(128, "git"))
    with pytest.raises(files.subprocess.CalledProcessError):
        files.staged_filename_matches([])


def test_content_source_keeps_both_write_fields() -> None:
    assert files.content_text("write", {"tool_input": {"content": "one", "new_string": "two"}}) == "onetwo"


def test_commit_denial_reports_filenames_without_file_bodies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert files.__file__ is not None
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("AGENT_SECRET_COMMIT_POLICY", raising=False)
    (tmp_path / ".env").write_text("non-sensitive test fixture\n")
    for arguments in (["git", "init", "--quiet"], ["git", "add", "--", ".env"]):
        subprocess.run(arguments, cwd=tmp_path, check=True, capture_output=True)
    result = subprocess.run(
        [sys.executable, "-I", "-B", files.__file__, "commit"],
        input=json.dumps({"tool_input": {"command": "git commit"}}),
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 2
    logs = list((tmp_path / "docs/logs/audit").glob("*.jsonl"))
    assert len(logs) == 1
    row = json.loads(logs[0].read_text())
    assert ".env" in result.stderr and ".env" in row["reason"]
    assert "Environment files may contain credentials." in row["reason"]
    assert "non-sensitive test fixture" not in result.stdout + result.stderr + logs[0].read_text()


def test_blocked_audit_rows_preserve_schema_and_append(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(tmp_path)})
    audit.blocked("Bash", "first", "reason", "hook.sh", "session")
    audit.blocked("Bash", "second", "reason", "hook.sh", "")
    paths = list((tmp_path / "docs/logs/audit").glob("*.jsonl"))
    assert len(paths) == 1
    rows = [json.loads(line) for line in paths[0].read_text().splitlines()]
    assert [row["input"] for row in rows] == ["first", "second"]
    assert rows[0] | {"ts": "time"} == {
        "ts": "time",
        "event": "Blocked",
        "status": "blocked",
        "tool": "Bash",
        "input": "first",
        "reason": "reason",
        "hook": "hook.sh",
        "session": "session",
    }
    assert rows[0]["ts"].endswith("Z")
    assert rows[1]["session"] == ""


@pytest.mark.parametrize(
    "source,expected",
    [
        ("git status", ["git status"]),
        ("", []),
        ("a | b | c", ["a", "b", "c"]),
        ("a && b && c", ["a", "b", "c"]),
        ("a; b || c", ["a", "b", "c"]),
        ("a & b", ["a", "b"]),
        ("a | b && c", ["a", "b", "c"]),
        ("a 2>&1", ["a 2>&1"]),
        ("a >&2", ["a >&2"]),
        ("echo 'a; b | c && d'", ["echo 'a; b | c && d'"]),
        ('echo "a; b | c && d"', ['echo "a; b | c && d"']),
        (r"echo a \| b \; c \& d", [r"echo a \| b \; c \& d"]),
        (
            "git commit -m 'fix: update' && git push origin topic",
            ["git commit -m 'fix: update'", "git push origin topic"],
        ),
    ],
)
def test_ast_command_boundaries_preserve_literals(source: str, expected: list[str]) -> None:
    assert [command.raw for command in hook_translation.shell_syntax.parse(source)] == expected


def test_redirect_paths_are_inspected_separately_from_command_arguments() -> None:
    command = hook_translation.shell_syntax.parse("printf x > .env")[0]
    assert command.arguments == ("printf", "x")
    assert command.redirections == (".env",)


@pytest.mark.parametrize("field", ["command", "cmd"])
@pytest.mark.parametrize("mode", ["allowed", "forbidden", "git", "commit"])
def test_shell_translation_calls_shared_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, mode: str
) -> None:
    monkeypatch.setenv("AGENT_HARNESS_ROOT", str(tmp_path))
    target = (
        hook_translation.guard_command
        if mode in {"allowed", "forbidden"}
        else hook_translation.guard_dangerous_git
        if mode == "git"
        else hook_translation.guard_file
    )
    check = Mock(return_value=2)
    monkeypatch.setattr(target, "check", check)
    payload = {"tool_input": {field: "git status"}, "session_id": "session-one"}
    assert hook_translation.dispatch("shell", [mode], payload) == 2
    translated = {"tool_name": "Bash", "tool_input": {"command": "git status"}, "session_id": "session-one"}
    if mode == "git":
        check.assert_called_once_with(translated)
    else:
        check.assert_called_once_with(mode, translated, tmp_path / ".claude/hooks")


def test_adapter_applies_payload_cwd_before_enforcement(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path.parent)
    payload = {"cwd": str(tmp_path), "tool_input": {"cmd": "git status"}}
    monkeypatch.setattr(hook_translation.sys, "stdin", io.StringIO(json.dumps(payload)))
    observed = []
    monkeypatch.setattr(hook_translation.guard_dangerous_git, "check", lambda _: observed.append(Path.cwd()) or 0)
    assert hook_translation.main(["shell", "git"]) == 0
    assert observed == [tmp_path]


@pytest.mark.parametrize("raw", ["{", "null", "[]", '{"tool_input":true}'])
def test_adapter_rejects_invalid_input(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setattr(hook_translation.sys, "stdin", io.StringIO(raw))
    assert hook_translation.main(["shell", "git"]) == 2


def test_lint_only_checks_existing_supported_patch_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "source.py").touch()
    (tmp_path / "unknown.bin").touch()
    check = Mock(return_value=())
    monkeypatch.setattr(hook_translation.lint_format, "check_file", check)
    patch = "\n".join(f"*** Update File: {name}" for name in ("source.py", "unknown.bin", "missing.py"))
    assert hook_translation.lint({"tool_input": {"command": patch}}) == 0
    check.assert_called_once_with("py", tmp_path / "source.py")


@pytest.mark.parametrize(
    "module,mode,identifier",
    [
        (hook_translation.guard_command, "allowed", "guard_allowed_commands.sh"),
        (hook_translation.guard_command, "forbidden", "guard_forbidden_commands.sh"),
        (hook_translation.guard_dangerous_git, "", "guard_dangerous_git.sh"),
        (hook_translation.guard_file, "commit", "guard_secret_commit.sh"),
        (hook_translation.guard_file, "harness", "guard_harness_files.sh"),
    ],
)
def test_malformed_guard_input_remains_auditable(
    monkeypatch: pytest.MonkeyPatch, module: ModuleType, mode: str, identifier: str
) -> None:
    monkeypatch.setattr(module.sys, "stdin", io.StringIO("{"))
    monkeypatch.setattr(module.sys, "argv", ["hook"])
    blocked = Mock()
    monkeypatch.setattr(module.audit_log, "blocked", blocked)
    assert (module.main([mode]) if mode else module.main()) == 2
    blocked.assert_called_once()
    assert blocked.call_args.args[1] == ""
    assert blocked.call_args.args[3] == identifier
