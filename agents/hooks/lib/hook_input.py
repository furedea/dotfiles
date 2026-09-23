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
FILE_FIELDS = ("file_path", "path", "notebook_path")


def file_path(values: dict) -> str:
    """Return the single file a tool names, whichever provider field carries it."""
    return next((value for key in FILE_FIELDS if isinstance(value := values.get(key), str) and value), "")


def _cwd(payload: dict) -> Path:
    value = payload.get("cwd")
    if not isinstance(value, str) or not value:
        return Path.cwd().resolve()
    return Path(value).expanduser().resolve()


def patch_body(values: dict, tool: str | None = None) -> str:
    """Return the single patch body or reject conflicting, unverifiable carriers.

    `patch` is the canonical field adapters normalize into. `input` and
    `command` are accepted only for apply_patch tools or when the content
    itself carries patch markers, so a plain shell command is never read
    as a patch.
    """
    found = {
        key: value for key in ("patch", "input", "command") if isinstance((value := values.get(key)), str) and value
    }
    bodies = set(found.values())
    if len(bodies) > 1:
        raise ValueError("conflicting patch fields in tool_input")
    body = next(iter(bodies), "")
    if tool == "apply_patch":
        if body and not patch_input.is_patch(body):
            raise ValueError("malformed patch input")
        return body
    if "patch" in found:
        if not patch_input.is_patch(body):
            raise ValueError("malformed patch input")
        return body
    return body if patch_input.is_patch(body) else ""


def _input_names(payload: dict) -> tuple[str, ...]:
    values = payload.get("tool_input")
    if values is None:
        return ()
    if not isinstance(values, dict):
        raise ValueError("tool_input must be an object")
    tool = payload.get("tool_name")
    if tool and tool not in EDIT_TOOLS:
        return ()
    names = list(patch_input.paths(patch_body(values, tool)))
    if name := file_path(values):
        names.append(name)
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
