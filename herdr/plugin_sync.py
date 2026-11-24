#!/usr/bin/env -S python3 -IB
"""Reconcile declared Herdr plugins while preserving state on failure."""

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

LIST_ARGUMENTS = ["plugin", "list", "--json"]


@dataclass(frozen=True, slots=True)
class Plugin:
    """An explicitly managed plugin: a GitHub revision, or a local path linked as is."""

    identifier: str
    source: str
    revision: str


def declared_plugins(arguments: list[str]) -> tuple[Plugin, ...]:
    """Parse the Home Manager declaration's identifier/source/revision triples."""
    if len(arguments) % 3 or any(argument in {"-h", "--help"} for argument in arguments):
        raise ValueError("Usage: plugin_sync.py [<PLUGIN_ID> <GITHUB_SOURCE> <GIT_REF>]...")
    return tuple(Plugin(*arguments[index : index + 3]) for index in range(0, len(arguments), 3))


def installed_revision(item: dict) -> str:
    """Identify an installed plugin by its commit, or by its root when it was linked locally."""
    source = item.get("source") or {}
    return source.get("resolved_commit") or (item.get("plugin_root", "") if source.get("kind") == "local" else "")


def changes(
    declared: tuple[Plugin, ...], installed: dict[str, str], managed: set[str]
) -> tuple[tuple[Plugin, ...], tuple[str, ...]]:
    """Select updates and removals, never claiming unmanaged plugins."""
    updates = tuple(plugin for plugin in declared if installed.get(plugin.identifier) != plugin.revision)
    retained = {plugin.identifier for plugin in declared}
    removed = tuple(sorted((managed & installed.keys()) - retained))
    return updates, removed


def install_arguments(executable: str, plugin: Plugin) -> list[str]:
    """Link a locally built plugin; install any other from its pinned GitHub revision."""
    if plugin.source.startswith("/"):
        return [executable, "plugin", "link", plugin.source]
    return [executable, "plugin", "install", plugin.source, "--ref", plugin.revision, "--yes"]


def installed_revisions(executable: str) -> dict[str, str]:
    """Read each installed plugin's identity from the Herdr CLI."""
    payload = json.loads(subprocess.check_output([executable, *LIST_ARGUMENTS], text=True))
    return {item["plugin_id"]: installed_revision(item) for item in payload.get("result", {}).get("plugins", [])}


def synchronize(declared: tuple[Plugin, ...], state: Path, executable: str) -> None:
    """Apply installs before removals and atomically publish the completed declaration."""
    state.parent.mkdir(parents=True, exist_ok=True)
    installed = installed_revisions(executable)
    managed = set(state.read_text().splitlines()) if state.is_file() else set()
    updates, removed = changes(declared, installed, managed)
    for plugin in updates:
        subprocess.run(install_arguments(executable, plugin), check=True)
    for identifier in removed:
        subprocess.run([executable, "plugin", "uninstall", identifier], check=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=state.parent, prefix=f"{state.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.writelines(f"{plugin.identifier}\n" for plugin in declared)
        temporary.replace(state)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(arguments: list[str]) -> int:
    """Run reconciliation using the configured Herdr executable and state location."""
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    state = Path(os.environ.get("HERDR_PLUGIN_SYNC_STATE_FILE", str(base / "home-manager/herdr_plugins")))
    try:
        synchronize(declared_plugins(arguments), state, os.environ.get("HERDR_BIN", "herdr"))
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode > 0 else 1
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
