"""Herdr must not contact its vendor without an explicit opt-in."""

import tomllib

from tests.runtime import REPO_ROOT

UPDATE = tomllib.loads((REPO_ROOT / "herdr/config.toml").read_text()).get("update", {})


def test_release_version_check_is_disabled() -> None:
    assert UPDATE.get("version_check") is False


def test_agent_detection_manifest_download_is_disabled() -> None:
    assert UPDATE.get("manifest_check") is False
