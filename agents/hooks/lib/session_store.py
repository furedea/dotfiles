"""Private, bounded verification state with atomic replacement and process leases."""

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
import uuid

from session_snapshot import Snapshot, capture


SCHEMA = 1
RETENTION_SECONDS = 7 * 24 * 60 * 60
LOG_LIMIT_BYTES = 1024 * 1024
TOTAL_LOG_LIMIT_BYTES = 100 * LOG_LIMIT_BYTES


class StateError(ValueError):
    """Verification registration or evidence cannot be trusted."""


@dataclass(frozen=True, slots=True)
class Run:
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
            Path(record["log"]).name
            for record in value.get("checks", {}).values()
            if isinstance(record, dict) and isinstance(record.get("log"), str)
        }
        for path in log_files(self.directory):
            if path.name not in retained:
                path.unlink(missing_ok=True)

    def bind(self, session_id: str, *, resuming: bool, clearing: bool = False) -> None:
        """Bind once; resume copies the original baseline before any tool executes."""
        if not session_id or len(session_id) > 256:
            raise StateError("Missing or invalid provider session ID")
        results = self.results()
        if existing := results.get("session_id"):
            if existing != session_id and not clearing:
                raise StateError("Provider session differs from the registered session")
            if clearing:
                results["session_id"] = session_id
                self.save_results(results)
            return
        if resuming or results.get("resume_pending"):
            previous = self.previous_session(session_id)
            if previous is None:
                results.update(revalidate_all=True, checks={})
            else:
                baseline = read_json(self.directory / "baseline.json")
                baseline["files"] = previous.baseline.to_json()
                atomic_json(self.directory / "baseline.json", baseline)
                results.update(checks=previous.results()["checks"])
                results["revalidate_all"] = previous.results().get("revalidate_all", False)
        results.update(session_id=session_id, resume_pending=False)
        self.save_results(results)

    def previous_session(self, session_id: str) -> Run | None:
        candidates = sorted(self.directory.parent.iterdir(), key=lambda path: path.name, reverse=True)
        for directory in candidates:
            if directory == self.directory or not directory.is_dir() or directory.is_symlink():
                continue
            previous = load(directory)
            result = previous.results()
            if previous.provider == self.provider and result.get("session_id") == session_id:
                if not result.get("ended_at") or time.time() - result["ended_at"] > RETENTION_SECONDS:
                    continue
                return previous
        return None

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
    def lock(self) -> Iterator[None]:
        with file_lock(self.directory / ".lock"):
            yield

    @contextmanager
    def lease(self) -> Iterator[None]:
        """The launcher holds this across the complete child process lifetime."""
        with file_lock(self.directory / ".lease"):
            yield


def state_directory() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))).expanduser()
    if not base.is_absolute():
        raise StateError("XDG_STATE_HOME must be absolute")
    return base / "agent-harness/verification"


def worktree_id(root: Path) -> str:
    return hashlib.sha256(os.fsencode(root.resolve())).hexdigest()[:32]


def register(root: Path, provider: str, *, resuming: bool = False) -> Run:
    """Persist a baseline before the provider process is allowed to start."""
    root = root.resolve()
    base = state_directory()
    if base.resolve().is_relative_to(root):
        raise StateError("Verification state must be outside the worktree")
    baseline = capture(root)
    private_directory(base)
    private_directory(base / worktree_id(root))
    directory = base / worktree_id(root) / f"{time.time_ns():020d}-{uuid.uuid4().hex}"
    private_directory(directory)
    atomic_json(
        directory / "baseline.json",
        {
            "schema": SCHEMA,
            "root": str(root),
            "provider": provider,
            "created_at": time.time(),
            "files": baseline.to_json(),
        },
    )
    run = Run(directory, root, provider)
    run.save_results({"checks": {}, "resume_pending": resuming, "revalidate_all": False})
    return run


def load(directory: Path) -> Run:
    base = state_directory()
    if directory.parent.parent != base or directory.is_symlink() or directory.parent.is_symlink():
        raise StateError("Invalid verification registration path")
    record = read_json(directory / "baseline.json")
    root = Path(record["root"])
    if record.get("schema") != SCHEMA or worktree_id(root) != directory.parent.name:
        raise StateError("Invalid verification baseline")
    return Run(directory, root, record["provider"])


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
    """Retain live registrations; bound logs globally without dropping failure status."""
    base = state_directory()
    if not base.exists():
        return
    private_directory(base)
    current = time.time() if now is None else now
    with file_lock(base / ".gc.lock"):
        for directory in tuple(base.glob("*/*")):
            if not directory.is_dir() or directory.is_symlink() or directory.parent.is_symlink():
                continue
            prune_run(directory, current)
        logs = [path for directory in run_directories(base) for path in log_files(directory)]
        total = sum(path.stat().st_size for path in logs)
        for path in sorted(logs, key=lambda value: value.stat().st_mtime_ns):
            if total <= TOTAL_LOG_LIMIT_BYTES:
                break
            total -= path.stat().st_size
            path.unlink(missing_ok=True)


def run_directories(base: Path) -> Iterator[Path]:
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


def prune_run(directory: Path, now: float) -> None:
    try:
        with file_lock(directory / ".lease", blocking=False), file_lock(directory / ".lock", blocking=False):
            run = load(directory)
            results = run.results()
            if not results.get("ended_at"):
                # A crashed launch gets a full retention interval after discovery.
                run.end(now=now)
            elif now - results["ended_at"] > RETENTION_SECONDS:
                shutil.rmtree(directory)
    except OSError, StateError, KeyError, TypeError:
        return
