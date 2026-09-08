#!/usr/bin/env python3
"""Filter a unified git diff to a selected subset of hunks.

The output is a valid diff suitable for ``git apply --cached``. Selection is
specified as JSON, either inline or as a path to a .json file.

Usage:
    build_partial_patch.py <diff_file> <selection>

Selection schema (JSON array):
    [
      {"file": "path/to/file.py", "hunks": [1, 3]},   # 1-based hunk indices
      {"file": "path/to/other.py", "hunks": "all"}    # whole-file
    ]

Hunks are numbered 1..N per file, in the order they appear in the input diff.
A binary diff or a pure rename without content hunks must use ``"hunks": "all"``.

Exit codes:
    0  success
    1  IO/parse error
    2  selection references an unknown file or hunk
"""

from __future__ import annotations

import codecs
import json
import re
import sys
from pathlib import Path


_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
_FILE_HEADER = re.compile(r"^diff --git ")


def parse_diff(text: str) -> list[dict]:
    """Split a unified diff into one entry per file.

    Each entry has:
        path:    target path (the ``b/`` side)
        header:  list of lines before the first hunk (diff/index/---/+++/...)
        hunks:   list of hunks; each hunk is a list of lines starting with ``@@``
    """
    files: list[dict] = []
    current: dict | None = None
    in_hunk = False
    for line in text.splitlines(keepends=True):
        if _FILE_HEADER.match(line):
            current = {"path": None, "header": [line], "hunks": []}
            files.append(current)
            in_hunk = False
            continue
        if current is None:
            continue
        if _HUNK_HEADER.match(line):
            current["hunks"].append([line])
            in_hunk = True
            continue
        if in_hunk:
            current["hunks"][-1].append(line)
        else:
            current["header"].append(line)
            if line.startswith(("--- ", "+++ ")) and line[4:].strip() != "/dev/null":
                current["path"] = _strip_prefix(_decode_path(line[4:].rstrip("\n").split("\t")[0]))
            elif line.startswith(("rename to ", "copy to ")):
                current["path"] = _decode_path(line.split(" to ", 1)[1].rstrip("\n"))
    for file in files:
        if file["path"] is None:
            file["path"] = _extract_path(file["header"][0])
    return files


def _extract_path(diff_git_line: str) -> str:
    # Binary and mode-only diffs have no +++ marker. Their paths agree unless
    # rename/copy metadata already supplied the destination.
    paths = diff_git_line.removeprefix("diff --git ").rstrip("\n")
    for boundary, character in enumerate(paths):
        if character != " ":
            continue
        try:
            source = _strip_prefix(_decode_path(paths[:boundary]))
            target = _strip_prefix(_decode_path(paths[boundary + 1 :]))
        except ValueError:
            continue
        if source == target:
            return target
    raise ValueError(f"cannot parse path from: {diff_git_line!r}")


def _decode_path(path: str) -> str:
    if not path.startswith('"'):
        return path
    if not path.endswith('"'):
        raise ValueError(f"unterminated Git path: {path!r}")
    # Git quotes UTF-8 bytes with C-style escapes, including octal sequences.
    return codecs.escape_decode(path[1:-1].encode())[0].decode("utf-8", errors="surrogateescape")


def _strip_prefix(path: str) -> str:
    prefix, separator, relative = path.partition("/")
    if not separator or not prefix or any(character.isspace() for character in prefix):
        raise ValueError(f"missing Git diff path prefix: {path!r}")
    return relative


def build_partial(files: list[dict], selection: list[dict]) -> str:
    by_path = {f["path"]: f for f in files}
    out: list[str] = []
    for entry in selection:
        path = entry["file"]
        if path not in by_path:
            print(
                f"unknown file in selection: {path}\navailable: {sorted(by_path)}",
                file=sys.stderr,
            )
            sys.exit(2)
        f = by_path[path]
        out.extend(f["header"])
        which = entry["hunks"]
        if which == "all":
            chosen = list(range(1, len(f["hunks"]) + 1))
        else:
            chosen = list(which)
        for idx in chosen:
            if idx < 1 or idx > len(f["hunks"]):
                print(
                    f"hunk {idx} not present in {path} (have {len(f['hunks'])})",
                    file=sys.stderr,
                )
                sys.exit(2)
            out.extend(f["hunks"][idx - 1])
    return "".join(out)


def _load_selection(arg: str) -> list[dict]:
    p = Path(arg)
    if p.is_file():
        return json.loads(p.read_text())
    return json.loads(arg)


def main() -> None:
    if len(sys.argv) != 3:
        sys.stderr.write(__doc__ or "")
        sys.exit(1)
    diff_text = Path(sys.argv[1]).read_text()
    selection = _load_selection(sys.argv[2])
    files = parse_diff(diff_text)
    sys.stdout.write(build_partial(files, selection))


if __name__ == "__main__":
    main()
