"""Plugin reconciliation selects only explicitly managed changes."""

import pytest

from conftest import load_script_module


plugins = load_script_module("herdr/plugin_sync.py", "plugin_sync")


def test_matching_declared_plugin_needs_no_update() -> None:
    declared = (plugins.Plugin("review", "owner/review", "abc"),)
    assert plugins.changes(declared, {"review": "abc"}, {"review"}) == ((), ())


def test_missing_or_changed_plugin_is_installed_before_managed_removals() -> None:
    changed = plugins.Plugin("review", "owner/review", "new")
    assert plugins.changes((changed,), {"review": "old", "removed": "abc"}, {"review", "removed"}) == (
        (changed,),
        ("removed",),
    )


def test_unmanaged_plugins_are_never_removed() -> None:
    assert plugins.changes((), {"personal": "abc"}, set()) == ((), ())


def test_managed_but_already_missing_plugins_need_no_removal() -> None:
    assert plugins.changes((), {}, {"removed"}) == ((), ())


@pytest.mark.parametrize("arguments", [["identifier"], ["identifier", "source"]])
def test_incomplete_declarations_are_rejected(arguments: list[str]) -> None:
    with pytest.raises(ValueError, match="Usage"):
        plugins.declared_plugins(arguments)
