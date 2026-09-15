"""Post identifiers, exact search results, and editor saves have distinct contracts."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from tests.runtime import load_script_module

esa = load_script_module("zsh/esa.py", "esa_editor")


@pytest.mark.parametrize("number", [None, True, False, "", "../1", 0, -1, "1; echo unsafe"])
def test_invalid_post_numbers_never_reach_the_cli(number: object) -> None:
    with pytest.raises(ValueError, match="post number"):
        esa.post_number(number)


@pytest.mark.parametrize(
    "matches",
    [
        [],
        [{"category": "Members/k-shigyo", "name": "other", "number": 1}],
        [{"category": "Members/k-shigyo", "name": "note", "number": 1}] * 2,
    ],
)
def test_named_post_search_requires_exactly_one_matching_result(matches: list[dict], mocker: MockerFixture) -> None:
    mocker.patch.object(esa, "esa_json", return_value={"posts": matches})
    with pytest.raises(ValueError, match="uniquely"):
        esa.find_post("Members/k-shigyo/note")


def test_failed_final_save_retains_the_previous_shell_state(mocker: MockerFixture, tmp_path: Path) -> None:
    result = tmp_path / "result"
    result.touch()
    mocker.patch.object(esa, "execute", side_effect=esa.subprocess.CalledProcessError(1, "esa"))
    assert esa.main([str(result), "1515", "es"]) == 1
    assert result.read_text() == ""
