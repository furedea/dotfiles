"""Policy regexes keep their POSIX ERE dialect while each decision spawns a bounded number of processes."""

import json
import os
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from tests.runtime import REPO_ROOT, load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
policy = guard.command_policy
ALLOWED_RULES = REPO_ROOT / "agents/hooks/rules/allowed_commands.json"


def grep_calls(spy: Mock) -> int:
    return sum(1 for call in spy.call_args_list if Path(str(call.args[0][0])).name == "grep")


def test_loading_validates_every_pattern_with_one_grep(mocker: MockerFixture) -> None:
    spy = mocker.spy(subprocess, "run")
    rules = policy.load_rules(ALLOWED_RULES)
    assert sum(len(rule["patterns"]) for rule in rules) > 30
    assert grep_calls(spy) == 1


def test_loading_still_rejects_an_invalid_pattern_among_valid_ones(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    rules = [
        {"patterns": ["^ok$"], "justification": "valid"},
        {"patterns": ["^fine$", "["], "justification": "broken"},
    ]
    path.write_text(json.dumps({"version": 1, "rules": rules}))
    with pytest.raises(ValueError, match="invalid command policy"):
        policy.load_rules(path)


def test_unmatched_commands_are_judged_with_one_grep(mocker: MockerFixture) -> None:
    rules = policy.load_rules(ALLOWED_RULES)
    spy = mocker.spy(subprocess, "run")
    assert policy.regex_reason("gh pr review 42 --approve", rules) == ""
    assert grep_calls(spy) == 1


def test_matched_commands_spawn_at_most_one_grep_per_rule(mocker: MockerFixture) -> None:
    rules = policy.load_rules(ALLOWED_RULES)
    spy = mocker.spy(subprocess, "run")
    assert policy.regex_reason("gh pr list", rules)
    assert grep_calls(spy) <= 1 + len(rules)


def test_reason_reports_the_first_matching_rule_in_order() -> None:
    rules = [
        {"patterns": ["^git status$"], "justification": "first"},
        {"patterns": ["^git status$", "^git log( .*)?$"], "justification": "second"},
    ]
    assert policy.regex_reason("git status", rules) == "first"
    assert policy.regex_reason("git log --oneline", rules) == "second"
    assert policy.regex_reason("git push", rules) == ""


def test_trailing_stderr_redirections_stay_ignored() -> None:
    rules = [{"patterns": ["^git status$"], "justification": "status"}]
    assert policy.regex_reason("git status 2>&1", rules) == "status"
    assert policy.regex_reason("git status > out.txt", rules) == ""


def test_empty_pattern_lists_never_match() -> None:
    assert policy.any_regex_matches((), "anything") is False


def test_only_programs_that_reach_past_the_sandbox_are_governed() -> None:
    rules = policy.load_rules(ALLOWED_RULES)
    assert policy.governed_programs(rules) == {"gh", "curl", "wget", "herdr"}


def test_an_invalid_program_list_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    rules = [{"patterns": ["^ok$"], "programs": ["", "rg"], "justification": "broken"}]
    path.write_text(json.dumps({"version": 1, "rules": rules}))
    with pytest.raises(ValueError, match="invalid command policy"):
        policy.load_rules(path)


def test_rules_judge_the_whole_segment_rather_than_any_single_line() -> None:
    rules = [{"patterns": ["^git status$"], "justification": "status"}]
    assert policy.regex_reason('git commit -m "subject\ngit status\n"', rules) == ""


def test_anchored_rules_match_multi_line_quoted_arguments() -> None:
    rules = [{"patterns": ['^git commit -m "[^"]*"$'], "justification": "commit"}]
    assert policy.regex_reason('git commit -m "subject\n\nCo-Authored-By: X <x@y>"', rules) == "commit"


@pytest.mark.parametrize("grep_directory", ["", "/usr/bin"], ids=["PATH grep", "macOS grep first"])
def test_a_multi_line_command_is_judged_as_one_line_by_any_grep(
    monkeypatch: pytest.MonkeyPatch, grep_directory: str
) -> None:
    if grep_directory:
        monkeypatch.setenv("PATH", f"{grep_directory}{os.pathsep}{os.environ['PATH']}")
    assert policy.regex_matches("^gh api user$", "gh api user") is True
    assert policy.regex_matches("^gh api 'repos/x .*$", "gh api 'repos/x\n' --method DELETE") is True
    assert policy.regex_matches("^gh api 'repos/x$", "gh api 'repos/x\n' --method DELETE") is False
    assert policy.regex_matches("^--method DELETE$", "gh api 'repos/x\n' --method DELETE") is False
