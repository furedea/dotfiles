"""Private, bounded verification state keyed by native provider sessions."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from session_snapshot import Snapshot, capture


SCHEMA = 1
RETENTION_SECONDS = 7 * 24 * 60 * 60
LOG_LIMIT_BYTES = 1024 * 1024
TOTAL_LOG_LIMIT_BYTES = 100 * LOG_LIMIT_BYTES


class StateError(ValueError):
    """Verification registration or evidence cannot be trusted."""


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """One registered provider session: its baseline, receipts, logs, and lock."""

    directory: Path
    root: Path
    provider: str

    @property
    def baseline(self) -> Snapshot:
        return Snapshot.from_json(read_json(self.directory / "baseline.json")["files"])

    def results(self) -> dict:
        value = read_json(self.directory / "results.json")
        if not isinstance(value.get("checks"), dict):
            raise StateError("Invalid check results")
        return value

    def save_results(self, value: dict) -> None:
        atomic_json(self.directory / "results.json", value)
        retained = {
            Path(receipt["log"]).name
            for receipt in value.get("checks", {}).values()
            if isinstance(receipt, dict) and isinstance(receipt.get("log"), str)
        }
        for path in log_files(self.directory):
            if path.name not in retained:
                path.unlink(missing_ok=True)

    def touch(self) -> None:
        """Keep active sessions without a parent process or a per-tool snapshot."""
        os.utime(self.directory, None)

    def end(self, *, now: float | None = None) -> None:
        results = self.results()
        results["ended_at"] = time.time() if now is None else now
        self.save_results(results)

    def write_log(self, check_id: str, output: str) -> Path:
        directory = self.directory / "logs"
        private_directory(directory)
        filename = hashlib.sha256(check_id.encode()).hexdigest()[:24] + ".log"
        data = output.encode("utf-8", errors="replace")
        if len(data) > LOG_LIMIT_BYTES:
            header = b"[earlier output truncated]\n"
            data = header + data[-(LOG_LIMIT_BYTES - len(header)) :]
        path = directory / filename
        atomic_bytes(path, data)
        return path

    @contextmanager
    def lock(self, *, blocking: bool = True) -> Iterator[None]:
        with file_lock(self.directory / ".lock", blocking=blocking):
            yield


def state_directory() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))).expanduser()
    if not base.is_absolute():
        raise StateError("XDG_STATE_HOME must be absolute")
    return base / "agent-harness/verification"


def worktree_id(root: Path) -> str:
    return hashlib.sha256(os.fsencode(root.resolve())).hexdigest()[:32]


def session_directory(root: Path, provider: str, session_id: str) -> Path:
    if (
        provider not in {"codex", "claude", "devin"}
        or not isinstance(session_id, str)
        or not 0 < len(session_id) <= 256
    ):
        raise StateError("Missing or invalid provider session ID")
    identity = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    return state_directory() / worktree_id(root) / f"{provider}-{identity}"


def register(root: Path, provider: str, session_id: str, *, resuming: bool = False) -> SessionRecord:
    """Register once from SessionStart; repeated delivery preserves pending work."""
    root = root.resolve()
    base = state_directory()
    if base.resolve().is_relative_to(root):
        raise StateError("Verification state must be outside the worktree")
    directory = session_directory(root, provider, session_id)
    private_directory(base)
    private_directory(directory.parent)
    with file_lock(directory.parent / ".register.lock", blocking=False):
        if directory.exists() or directory.is_symlink():
            record = load(directory)
            with record.lock(blocking=False):
                results = record.results()
                results.pop("ended_at", None)
                record.save_results(results)
                record.touch()
            return record
        baseline = capture(root)
        with tempfile.TemporaryDirectory(prefix=".register-", dir=directory.parent) as temporary:
            staging = Path(temporary)
            atomic_json(
                staging / "baseline.json",
                {
                    "schema": SCHEMA,
                    "root": str(root),
                    "provider": provider,
                    "created_at": time.time(),
                    "files": baseline.to_json(),
                },
            )
            atomic_json(staging / "results.json", {"checks": {}, "session_id": session_id, "revalidate_all": resuming})
            atomic_bytes(staging / ".lock", b"")
            os.rename(staging, directory)
        return SessionRecord(directory, root, provider)


def load(directory: Path) -> SessionRecord:
    base = state_directory()
    if directory.parent.parent != base or directory.is_symlink() or directory.parent.is_symlink():
        raise StateError("Invalid verification registration path")
    baseline = read_json(directory / "baseline.json")
    root = Path(baseline["root"])
    if baseline.get("schema") != SCHEMA or worktree_id(root) != directory.parent.name:
        raise StateError("Invalid verification baseline")
    try:
        Snapshot.from_json(baseline["files"])
    except (ValueError, TypeError, KeyError) as error:
        raise StateError("Invalid verification baseline files") from error
    return SessionRecord(directory, root, baseline["provider"])


def private_directory(path: Path) -> None:
    if path.is_symlink():
        raise StateError(f"State directory is a symlink: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise StateError(f"State directory has a different owner: {path}")
    path.chmod(0o700)


def read_json(path: Path) -> dict:
    if path.is_symlink():
        raise StateError(f"State file is a symlink: {path}")
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("Expected an object")
        return value
    except (OSError, ValueError) as error:
        raise StateError(f"Unreadable verification record: {path}") from error


def atomic_json(path: Path, value: dict) -> None:
    atomic_bytes(path, json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode())


def atomic_bytes(path: Path, value: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def file_lock(path: Path, *, blocking: bool = True) -> Iterator[None]:
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def prune(*, now: float | None = None) -> None:
    """Expire ended or inactive sessions and bound logs without dropping failure status."""
    base = state_directory()
    if not base.exists():
        return
    private_directory(base)
    current = time.time() if now is None else now
    with file_lock(base / ".gc.lock"):
        for directory in tuple(base.glob("*/*")):
            if not directory.is_dir() or directory.is_symlink() or directory.parent.is_symlink():
                continue
            prune_record(directory, current)
        logs = [path for directory in record_directories(base) for path in log_files(directory)]
        total = sum(path.stat().st_size for path in logs)
        for path in sorted(logs, key=lambda value: value.stat().st_mtime_ns):
            if total <= TOTAL_LOG_LIMIT_BYTES:
                break
            total -= path.stat().st_size
            path.unlink(missing_ok=True)


def record_directories(base: Path) -> Iterator[Path]:
    for worktree in base.iterdir():
        if worktree.is_symlink() or not worktree.is_dir():
            continue
        for directory in worktree.iterdir():
            if not directory.is_symlink() and directory.is_dir():
                yield directory


def log_files(directory: Path) -> tuple[Path, ...]:
    logs = directory / "logs"
    if logs.is_symlink() or not logs.is_dir():
        return ()
    return tuple(path for path in logs.glob("*.log") if not path.is_symlink() and path.is_file())


def prune_record(directory: Path, now: float) -> None:
    try:
        with file_lock(directory / ".lock", blocking=False):
            record = load(directory)
            results = record.results()
            last_seen = results.get("ended_at", directory.stat().st_mtime)
            if now - last_seen > RETENTION_SECONDS:
                shutil.rmtree(directory)
    except OSError, StateError, KeyError, TypeError:
        return
