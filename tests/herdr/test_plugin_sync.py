"""Plugin reconciliation selects only explicitly managed changes."""

import pytest
from tests.runtime import load_script_module

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


def test_local_plugin_is_current_when_linked_from_the_declared_path() -> None:
    declared = (plugins.Plugin("review", "/nix/store/new", "/nix/store/new"),)
    assert plugins.changes(declared, {"review": "/nix/store/new"}, {"review"}) == ((), ())


def test_local_plugin_is_relinked_when_its_path_changes() -> None:
    declared = (plugins.Plugin("review", "/nix/store/new", "/nix/store/new"),)
    assert plugins.changes(declared, {"review": "/nix/store/old"}, {"review"}) == (declared, ())


def test_installed_revision_is_the_commit_for_github_and_the_root_for_local() -> None:
    assert plugins.installed_revision({"source": {"resolved_commit": "abc"}, "plugin_root": "/r"}) == "abc"
    assert plugins.installed_revision({"source": {"kind": "local"}, "plugin_root": "/r"}) == "/r"
