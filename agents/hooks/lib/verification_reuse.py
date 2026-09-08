"""Opt-in Stop-gate reuse for stable local inputs within one session/worktree.

Ignored inputs, dependency installations and external services are not tracked.
Enable only for controlled local verification; force a run after environment changes.
Cache failures fall back to the original gate, never to a synthetic success.
Unchanged failures block once per session/worktree and remain explicitly unresolved.
Changed inputs or RUN_RELATED_TESTS_FORCE=1 start a new verification attempt.
"""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time


SCHEMA = 4


class UncacheableState(Exception):
    """The verification inputs cannot be fingerprinted safely."""


def git_output(root: Path, *arguments: str) -> bytes:
    """Read repository metadata without modifying the index or object database."""
    return subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
    ).stdout


def file_record(path: Path) -> bytes:
    """Hash regular files without following symbolic links."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return b"missing"
    if not stat.S_ISREG(metadata.st_mode):
        raise UncacheableState(f"Unsupported input: {path}")
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return f"file:{metadata.st_mode & 0o111}:{digest.hexdigest()}".encode()


def repository_digest(root: Path) -> str:
    """Fingerprint tracked and non-ignored untracked working-tree files."""
    paths = git_output(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    digest = hashlib.sha256()
    for name in sorted(set(paths.split(b"\0")) - {b""}):
        path = root / os.fsdecode(name)
        # Do not follow a symlinked parent of a tracked path either.
        if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
            raise UncacheableState(f"Symlinked parent: {path}")
        digest.update(name + b"\0" + file_record(path) + b"\0")
    return digest.hexdigest()


def verification_id(root: Path, hook: Path) -> str:
    """Include the selector implementation, resolved base and gate configuration."""
    base = os.environ.get("RUN_RELATED_TESTS_BASE_REF", "refs/remotes/origin/HEAD")
    environment = {
        key: value
        for key, value in os.environ.items()
        if (
            key.startswith("RUN_RELATED_TESTS_")
            and key
            not in {
                "RUN_RELATED_TESTS_FORCE",
                "RUN_RELATED_TESTS_REUSE",
            }
        )
        or key in {"PATH", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}
    }
    digest = hashlib.sha256(json.dumps(environment, sort_keys=True).encode())
    digest.update(repository_digest(root).encode())
    digest.update(git_output(root, "rev-parse", "HEAD"))
    digest.update(git_output(root, "merge-base", "HEAD", base))
    digest.update(str(hook).encode())
    for path in sorted(hook.parent.rglob("*")):
        if path.suffix in {".sh", ".py", ".json"} and path.is_file():
            digest.update(os.fsencode(path.relative_to(hook.parent)) + b"\0" + file_record(path))
    return digest.hexdigest()


def execute_gate(hook: Path, payload: bytes) -> subprocess.CompletedProcess:
    """Run the original gate, with recursive reuse disabled."""
    environment = dict(os.environ, RUN_RELATED_TESTS_REUSE="0")
    environment.pop("AGENT_VERIFICATION_STARTED_AT", None)
    return subprocess.run(["bash", str(hook)], input=payload, capture_output=True, env=environment)


def cache_directory(root: Path, session: str) -> Path:
    """Isolate records by canonical worktree and session without exposing their names."""
    key = hashlib.sha256(os.fsencode(root) + b"\0" + session.encode()).hexdigest()
    base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    directory = base / "agent-harness" / "verification-reuse" / key
    if directory.resolve().is_relative_to(root):
        raise UncacheableState("The cache must be outside the repository")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def load_record(path: Path) -> dict:
    """Treat missing, malformed and obsolete records as cache misses."""
    try:
        record = json.loads(path.read_text())
    except OSError, ValueError:
        return {}
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        return {}
    return record


def save_record(path: Path, record: dict) -> None:
    """Replace the record atomically while the caller holds the session lock."""
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(record, stream)
            stream.flush()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def successful(result: subprocess.CompletedProcess) -> bool:
    """Only the gate's explicit successful verification output is reusable."""
    try:
        output = json.loads(result.stdout)
    except ValueError:
        return False
    return (
        result.returncode == 0
        and isinstance(output, dict)
        and "decision" not in output
        and str(output.get("systemMessage", "")).startswith("Verification passed · total ")
    )


def notification(message: str) -> subprocess.CompletedProcess:
    """Return an informational Stop message, not a verification pass or block."""
    return subprocess.CompletedProcess([], 0, json.dumps({"systemMessage": message}).encode() + b"\n", b"")


def details_line(message: str) -> str:
    line = next((line for line in message.splitlines() if line.startswith("Details: ")), "")
    if line and not Path(line.removeprefix("Details: ")).is_dir():
        return "Details: unavailable (not retained or expired)"
    return line


def with_total(result: subprocess.CompletedProcess, elapsed: float) -> subprocess.CompletedProcess:
    """Include wrapper startup, fingerprinting and lock wait in the final hook duration."""
    try:
        output = json.loads(result.stdout)
    except ValueError:
        return result
    if not isinstance(output, dict):
        return result
    field = "reason" if output.get("decision") == "block" else "systemMessage"
    if not isinstance(output.get(field), str):
        return result
    lines = output[field].splitlines()
    if not lines:
        return result
    prefixes = [f"Verification {status} · total " for status in ("passed", "failed", "skipped")]
    prefixes += ["Verification reused · unchanged", "Verification unresolved · unchanged · not rerun"]
    prefix = next((prefix for prefix in prefixes if lines[0].startswith(prefix)), None)
    if prefix is None:
        return result
    separator = "" if prefix.endswith(" ") else " · "
    lines[0] = f"{prefix}{separator}{elapsed:.1f}s"
    output[field] = "\n".join(lines)
    return subprocess.CompletedProcess(
        result.args, result.returncode, json.dumps(output).encode() + b"\n", result.stderr
    )


def failure_reason(result: subprocess.CompletedProcess) -> str | None:
    """Accept only explicit gate failures; crashes or malformed output are not suppressible."""
    try:
        output = json.loads(result.stdout)
    except ValueError:
        return None
    if result.returncode != 0 or not isinstance(output, dict) or output.get("decision") != "block":
        return None
    reason = output.get("reason")
    return reason if isinstance(reason, str) and reason else None


def previous_notification(directory: Path, state_id: str) -> subprocess.CompletedProcess | None:
    """Keep unresolved failure notifications separate from successful evidence."""
    failure = load_record(directory / "failure.json")
    reason = failure.get("reason")
    if failure.get("id") == state_id and isinstance(reason, str) and reason:
        error = next(
            (line for line in reason.splitlines() if line.startswith("Error: ")),
            "Error: " + reason.splitlines()[0][:240],
        )
        details = details_line(reason)
        return notification(
            "Verification unresolved · unchanged · not rerun\n" + error + ("\n" + details if details else "")
        )
    success = load_record(directory / "result.json")
    if success.get("id") == state_id:
        summary = success.get("summary", "")
        lines = summary.splitlines()[1:] if isinstance(summary, str) else []
        lines = [line for line in lines if line and not line.startswith("Details:")]
        return notification("\n".join(["Verification reused · unchanged", *lines]))
    return None


def invalidate_records(directory: Path) -> None:
    """Invalidate before a new attempt, including forced attempts and interruptions."""
    save_record(directory / "result.json", {"schema": SCHEMA})
    save_record(directory / "failure.json", {"schema": SCHEMA})


def run_locked(hook: Path, payload: bytes, context: tuple[Path, Path]) -> subprocess.CompletedProcess:
    root, directory = context
    try:
        if os.environ.get("RUN_RELATED_TESTS_FORCE") == "1":
            invalidate_records(directory)
        before = verification_id(root, hook)
        previous = previous_notification(directory, before)
        if previous is not None:
            return previous
        invalidate_records(directory)
    except OSError, UncacheableState, subprocess.SubprocessError:
        return execute_gate(hook, payload)

    result = execute_gate(hook, payload)
    reason = failure_reason(result)
    if not successful(result) and reason is None:
        return result
    try:
        if verification_id(root, hook) == before:
            record = {"schema": SCHEMA, "id": before, "verified_at": time.time()}
            if reason is not None:
                save_record(directory / "failure.json", dict(record, reason=reason))
            else:
                record["summary"] = json.loads(result.stdout)["systemMessage"]
                save_record(directory / "result.json", record)
    except OSError, UncacheableState, subprocess.SubprocessError:
        pass
    return result


def run_gate(hook: Path, payload: bytes) -> subprocess.CompletedProcess:
    """Serialize verification and success records within a session/worktree."""
    try:
        event = json.loads(payload)
        session = event.get("session_id") if isinstance(event, dict) else None
        if not isinstance(session, str) or not session:
            return execute_gate(hook, payload)
        root = Path(os.fsdecode(git_output(Path.cwd(), "rev-parse", "--show-toplevel")).strip()).resolve()
        directory = cache_directory(root, session)
        with (directory / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return run_locked(hook, payload, (root, directory))
    except OSError, ValueError, UncacheableState, subprocess.SubprocessError:
        return execute_gate(hook, payload)


def main() -> int:
    started_at = time.time()
    try:
        supplied_start = float(os.environ.get("AGENT_VERIFICATION_STARTED_AT", started_at))
        if 0 < supplied_start <= started_at:
            started_at = supplied_start
    except ValueError:
        pass
    result = run_gate(Path(sys.argv[1]).resolve(), sys.stdin.buffer.read())
    result = with_total(result, time.time() - started_at)
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
