"""Capture verification inputs without storing source content or a Git index."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess


class SnapshotError(ValueError):
    """The worktree cannot provide a complete, stable verification snapshot."""


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Sorted path signatures for tracked and nonignored untracked files."""

    entries: tuple[tuple[str, str], ...]

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.entries, ensure_ascii=True).encode()).hexdigest()

    def changed_paths(self, current: Snapshot) -> tuple[str, ...]:
        before, after = dict(self.entries), dict(current.entries)
        return tuple(sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path)))

    def to_json(self) -> dict[str, str]:
        return dict(self.entries)

    @classmethod
    def from_json(cls, value: object) -> Snapshot:
        if not isinstance(value, dict) or not all(
            isinstance(path, str)
            and path
            and not Path(path).is_absolute()
            and ".." not in Path(path).parts
            and isinstance(signature, str)
            and signature
            for path, signature in value.items()
        ):
            raise SnapshotError("Invalid baseline file signatures")
        return cls(tuple(sorted(value.items())))


def repository_root(directory: Path) -> Path:
    """Resolve the actual worktree, independently of remote refs and shell state."""
    try:
        result = subprocess.check_output(
            ["git", "-c", "core.fsmonitor=false", "-C", str(directory), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return Path(os.fsdecode(result).rstrip("\n")).resolve()
    except (OSError, subprocess.CalledProcessError) as error:
        raise SnapshotError(f"No Git worktree at {directory}") from error


def capture(root: Path) -> Snapshot:
    """Hash actual files, including task edits committed after launch."""
    root = root.resolve()
    try:
        output = subprocess.check_output(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            stderr=subprocess.DEVNULL,
        )
        paths = sorted({os.fsdecode(path) for path in output.split(b"\0") if path})
        entries = tuple(
            (path, file_signature(root, root / path))
            for path in paths
            if (root / path).exists() or (root / path).is_symlink()
        )
        return Snapshot(entries)
    except (OSError, subprocess.CalledProcessError) as error:
        raise SnapshotError(f"Cannot snapshot {root}: {error}") from error


def file_signature(root: Path, path: Path) -> str:
    """Reject external inputs that a worktree snapshot cannot track reliably."""
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise SnapshotError(f"Snapshot input points outside the worktree: {path.relative_to(root)}")
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        if not resolved.is_file():
            raise SnapshotError(f"Unsupported directory or broken symlink: {path.relative_to(root)}")
        target = os.readlink(path)
        return f"link:{target}:{file_signature(root, resolved)}"
    if stat.S_ISDIR(metadata.st_mode) and (path / ".git").exists():
        return f"submodule:{capture(path).digest}"
    if not stat.S_ISREG(metadata.st_mode):
        raise SnapshotError(f"Unsupported snapshot input: {path.relative_to(root)}")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    if (metadata.st_ino, metadata.st_size, metadata.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise SnapshotError(f"Input changed while being read: {path.relative_to(root)}")
    return f"file:{bool(metadata.st_mode & 0o111)}:{digest}"
