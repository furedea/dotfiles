"""Normalize provider hook payloads into unique filesystem targets."""

import os
from pathlib import Path

import patch_input


EXTENSIONS = {
    ".py": "py",
    ".sh": "sh",
    ".js": "js",
    ".ts": "js",
    ".jsx": "js",
    ".tsx": "js",
    ".rs": "rs",
    ".nix": "nix",
    ".md": "md",
    ".markdown": "md",
    ".json": "json_toml",
    ".toml": "json_toml",
    ".yml": "gha",
    ".yaml": "gha",
    ".txt": "txt",
    ".lua": "lua",
    ".tex": "tex",
    ".bib": "tex",
    ".cls": "tex",
    ".sty": "tex",
}
EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch"})


def _cwd(payload: dict) -> Path:
    value = payload.get("cwd")
    if not isinstance(value, str) or not value:
        return Path.cwd().resolve()
    return Path(value).expanduser().resolve()


def _input_names(payload: dict) -> tuple[str, ...]:
    values = payload.get("tool_input")
    if not isinstance(values, dict):
        return ()
    tool = payload.get("tool_name")
    command = values.get("command")
    if isinstance(command, str) and (tool == "apply_patch" or not tool):
        return patch_input.paths(command)
    if tool not in EDIT_TOOLS and tool:
        return ()
    names: list[str] = []
    file_path = values.get("file_path") or values.get("path")
    if isinstance(file_path, str):
        names.append(file_path)
    edits = values.get("edits")
    if isinstance(edits, list):
        names.extend(
            item.get("file_path")
            for item in edits
            if isinstance(item, dict) and isinstance(item.get("file_path"), str)
        )
    return tuple(names)


def target_paths(payload: dict) -> tuple[Path, ...]:
    """Resolve provider paths against payload cwd and remove duplicate targets."""
    root = _cwd(payload)
    paths: list[Path] = []
    seen: set[str] = set()
    for name in _input_names(payload):
        path = Path(name).expanduser()
        path = (path if path.is_absolute() else root / path).resolve()
        key = os.path.normcase(os.fspath(path))
        if key not in seen:
            seen.add(key)
            paths.append(path)
    return tuple(paths)
