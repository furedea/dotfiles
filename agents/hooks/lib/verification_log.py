"""Private failure evidence with bounded retention and conservative deletion."""

import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
import time


RETENTION_SECONDS = 604800
LIMIT_KIB = 102400
OUTPUT_LIMIT_BYTES = 1048576
KNOWN_FILE = re.compile(r"(?:\d+\.(?:command|output)\.log|\.complete)\Z")


def prepare_directory(root: Path) -> Path | None:
    """Create a private per-worktree log directory outside verification inputs."""
    try:
        root = root.resolve(strict=True)
        base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "agent-harness/verification"
        if base.resolve().is_relative_to(root):
            return None
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", root.name)[:48] or "project"
        key = hashlib.sha256(os.fsencode(root)).hexdigest()
        directory = base / f"{slug}-{key}"
        if directory.is_symlink():
            return None
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        return Path(tempfile.mkdtemp(dir=directory, prefix=f"failure-{int(time.time())}-"))
    except OSError:
        return None


def remove_completed(directory: Path) -> None:
    """Delete only recognized regular files after claiming a completed directory."""
    try:
        if directory.is_symlink() or not directory.is_dir():
            return
        complete = directory / ".complete"
        if complete.is_symlink() or not complete.is_file():
            return
        contents = tuple(directory.iterdir())
        if any(not KNOWN_FILE.fullmatch(path.name) or not stat.S_ISREG(path.lstat().st_mode) for path in contents):
            return
        claimed = directory.with_name(f".pruning-{directory.name}")
        if claimed.exists() or claimed.is_symlink():
            return
        directory.rename(claimed)
        for path in claimed.iterdir():
            if KNOWN_FILE.fullmatch(path.name) and stat.S_ISREG(path.lstat().st_mode):
                path.unlink()
        claimed.rmdir()
    except OSError:
        return


def size_kib(directory: Path) -> int:
    """Measure allocated regular-file storage without following links."""
    total = directory.stat().st_blocks * 512
    for parent, directories, files in os.walk(directory, followlinks=False):
        directories[:] = [name for name in directories if not (Path(parent) / name).is_symlink()]
        total += sum((Path(parent) / name).lstat().st_blocks * 512 for name in (*directories, *files))
    return (total + 1023) // 1024


def prune(base: Path, now: int) -> None:
    """Retain recent completed failures newest first within the worktree budget."""
    total = 0
    for directory in sorted(base.glob("failure-*"), reverse=True):
        try:
            complete = directory / ".complete"
            if directory.is_symlink() or complete.is_symlink() or not complete.is_file():
                continue
            completed = complete.read_text().strip()
            if not re.fullmatch(r"[0-9]{1,10}", completed):
                continue
            size = size_kib(directory)
            if now - int(completed) > RETENTION_SECONDS or total + size > LIMIT_KIB:
                remove_completed(directory)
            else:
                total += size
        except OSError:
            continue


def write_private(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def write_failure(directory: Path, number: int, command: str, output: str) -> None:
    """Store command metadata and a bounded tail of diagnostics as separate private files."""
    data = output.encode(errors="replace") + b"\n"
    if len(data) > OUTPUT_LIMIT_BYTES:
        data = (
            f"[Output truncated; retaining the final {OUTPUT_LIMIT_BYTES} bytes]\n".encode()
            + data[-OUTPUT_LIMIT_BYTES:]
        )
    write_private(directory / f"{number}.command.log", command.encode())
    write_private(directory / f"{number}.output.log", data)


def finish(directory: Path | None) -> str:
    """Mark a complete failure record before applying lazy retention."""
    if directory is None:
        return "Details: unavailable (log storage failed)"
    try:
        now = int(time.time())
        write_private(directory / ".complete", f"{now}\n".encode())
        prune(directory.parent, now)
        return f"Details: {directory}" if directory.is_dir() else "Details: unavailable (retention limit reached)"
    except OSError:
        return "Details: unavailable (log storage failed)"
