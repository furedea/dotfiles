"""Read-only gh api calls pass, in the forms CI log and file reads use, and anything that could write still asks."""

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
pytestmark = pytest.mark.usefixtures("isolated_project")

RAW = "-H 'Accept: application/vnd.github.raw'"
LOGS = '"repos/o/r/actions/jobs/$J/logs"'


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(
            'gh api --allow-escape-sequences "repos/o/r/actions/jobs/${J%% *}/logs"',
            id="a job log read through a quoted variable",
        ),
        pytest.param(
            "gh api --allow-escape-sequences repos/o/r/actions/jobs/1/logs",
            id="a job log read that allows escape sequences",
        ),
        pytest.param(
            "gh api repos/o/r/actions/runs/1/logs --allow-escape-sequences", id="escape sequences after the endpoint"
        ),
        pytest.param(
            f'gh api "repos/o/r/contents/$f" {RAW} > "$S/ref/x"',
            id="a raw file read through a quoted variable into a file",
        ),
        pytest.param(
            "gh api repos/o/r/actions/runs/123/attempts/2/jobs -q '.jobs[0].id'", id="a job id read with a jq filter"
        ),
    ],
)
def test_read_only_gh_api_forms_pass(command: str) -> None:
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "allow"


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(
            "gh api --allow-escape-sequences repos/o/r/actions/jobs/${J%% *}/logs",
            id="an unquoted variable that could split in a log read",
        ),
        pytest.param(
            "J='1 -X DELETE'; gh api --allow-escape-sequences repos/o/r/actions/jobs/$J/logs",
            id="an unquoted variable holding a method option in a log read",
        ),
        pytest.param(f'gh api repos/o/r/contents/$f {RAW} > "$S/ref/x"', id="an unquoted variable in a raw file read"),
        pytest.param(f"gh api --allow-escape-sequences {LOGS} -X DELETE", id="a method option after a log read"),
        pytest.param(f"gh api --allow-escape-sequences {LOGS} --method POST", id="a long method option after a read"),
        pytest.param(f"gh api --allow-escape-sequences {LOGS} -f body=x", id="a field after a log read"),
        pytest.param(f"gh api {LOGS} --allow-escape-sequences -F body=@f", id="a typed field after escape sequences"),
        pytest.param(f"gh api {LOGS} --raw-field body=x --allow-escape-sequences", id="a raw field before the flag"),
        pytest.param(
            f"gh api --input body.json {LOGS} --allow-escape-sequences", id="an input body before the endpoint"
        ),
        pytest.param(f"gh api {LOGS} --allow-escape-sequences --input body.json", id="an input body after the flag"),
        pytest.param('gh api --allow-escape-sequences graphql -f query="$Q"', id="GraphQL beside escape sequences"),
        pytest.param(f'gh api --allow-escape-sequences {LOGS} "$@"', id="spread arguments after a log read"),
        pytest.param(f"gh api --allow-escape-sequences {LOGS} $(cat opts)", id="a substitution after a log read"),
        pytest.param(f"gh api --allow-escape-sequences -X DELETE {LOGS}", id="a method option before the endpoint"),
        pytest.param(
            'eval "gh api --allow-escape-sequences repos/o/r/actions/jobs/$J/logs"', id="a log read through eval"
        ),
    ],
)
def test_gh_api_forms_that_could_write_or_inject_ask(command: str) -> None:
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "ask"
