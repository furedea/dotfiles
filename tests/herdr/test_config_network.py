"""Herdr must not contact its vendor without an explicit opt-in."""

import tomllib

import pytest
from tests.runtime import REPO_ROOT

UPDATE = tomllib.loads((REPO_ROOT / "herdr/config.toml").read_text()).get("update", {})


@pytest.mark.parametrize("key", ["version_check", "manifest_check"])
def test_vendor_request_is_disabled(key: str) -> None:
    assert UPDATE.get(key) is False
