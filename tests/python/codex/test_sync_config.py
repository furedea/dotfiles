from pathlib import Path
from typing import Any

from tests.python.conftest import load_script_module


sync_config = load_script_module("codex/sync_config.py", "sync_config")


def test_merge_config_replaces_managed_keys_and_preserves_codex_owned_state() -> None:
    source = {
        "model": "gpt-5.4",
        "plugins": {"Documents": {"enabled": True}},
    }
    target = {
        "model": "gpt-5.3",
        "approval_policy": "on-request",
        "projects": {"/repo": {"trust_level": "trusted"}},
    }

    merged = sync_config.merge_config(source, target)

    assert merged == {
        "model": "gpt-5.4",
        "plugins": {"Documents": {"enabled": True}},
        "projects": {"/repo": {"trust_level": "trusted"}},
    }


def test_toml_document_quotes_special_keys_and_string_values() -> None:
    data: dict[str, Any] = {
        "model": "gpt-5.4",
        "notice": ["line one", "line\ttwo"],
        "nested-table": {
            "enabled": True,
            "max_count": 3,
        },
        "key with space": "a\nb",
    }

    document = sync_config.toml_document(data)

    assert 'model = "gpt-5.4"' in document
    assert '"key with space" = "a\\nb"' in document
    assert '"line\\ttwo"' in document
    assert "[nested-table]" in document
    assert "enabled = true" in document
    assert "max_count = 3" in document


def test_write_toml_creates_parent_directory_and_round_trips(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "config.toml"

    sync_config.write_toml(output, {"model": "gpt-5.4", "tui": {"enabled": False}})

    assert output.read_text(encoding="utf-8") == 'model = "gpt-5.4"\n\n[tui]\nenabled = false\n'
