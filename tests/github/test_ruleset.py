"""Contract of the source-controlled main branch ruleset."""

import json

import pytest

from tests.runtime import REPO_ROOT


ADMIN_ROLE_ID = 5


@pytest.fixture
def ruleset() -> dict:
    return json.loads((REPO_ROOT / "github/ruleset.json").read_text())


def test_pull_request_rule_requires_fresh_human_approval(ruleset: dict) -> None:
    rule = next(rule for rule in ruleset["rules"] if rule["type"] == "pull_request")
    parameters = rule["parameters"]
    assert parameters["required_approving_review_count"] == 1
    assert parameters["dismiss_stale_reviews_on_push"] is True
    assert parameters["require_last_push_approval"] is True


def test_only_repository_admins_bypass_and_only_through_a_pull_request(ruleset: dict) -> None:
    assert ruleset["bypass_actors"] == [
        {"actor_id": ADMIN_ROLE_ID, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}
    ]
