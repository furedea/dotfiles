#!/usr/bin/env -S python3 -IB
"""Reconcile declared Herdr plugins while preserving state on failure."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


@dataclass(frozen=True, slots=True)
class Plugin:
    """An explicitly managed plugin revision."""

    identifier: str
    source: str
    revision: str


def declared_plugins(arguments: list[str]) -> tuple[Plugin, ...]:
    """Parse the Home Manager declaration's identifier/source/revision triples."""
    if len(arguments) % 3 or any(argument in {"-h", "--help"} for argument in arguments):
        raise ValueError("Usage: sync_plugins.py [<PLUGIN_ID> <GITHUB_SOURCE> <GIT_REF>]...")
    return tuple(Plugin(*arguments[index : index + 3]) for index in range(0, len(arguments), 3))


def changes(
    declared: tuple[Plugin, ...], installed: dict[str, str], managed: set[str]
) -> tuple[tuple[Plugin, ...], tuple[str, ...]]:
    """Select updates and removals, never claiming unmanaged plugins."""
    updates = tuple(plugin for plugin in declared if installed.get(plugin.identifier) != plugin.revision)
    retained = {plugin.identifier for plugin in declared}
    removed = tuple(sorted((managed & installed.keys()) - retained))
    return updates, removed


def synchronize(declared: tuple[Plugin, ...], state: Path, executable: str) -> None:
    """Apply installs before removals and atomically publish the completed declaration."""
    state.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(subprocess.check_output([executable, "plugin", "list", "--json"], text=True))
    installed = {
        item["plugin_id"]: (item.get("source") or {}).get("resolved_commit", "")
        for item in payload.get("result", {}).get("plugins", [])
    }
    managed = set(state.read_text().splitlines()) if state.is_file() else set()
    updates, removed = changes(declared, installed, managed)
    for plugin in updates:
        subprocess.run([executable, "plugin", "install", plugin.source, "--ref", plugin.revision, "--yes"], check=True)
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
