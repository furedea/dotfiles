"""Policy regexes keep their POSIX ERE dialect while each decision spawns a bounded number of processes."""

import json
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
    return sum(1 for call in spy.call_args_list if call.args[0][0] == "grep")


def test_loading_validates_every_pattern_with_one_grep(mocker: MockerFixture) -> None:
    spy = mocker.spy(subprocess, "run")
    rules = policy.load_rules(ALLOWED_RULES)
    assert sum(len(rule["patterns"]) for rule in rules) > 100
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
