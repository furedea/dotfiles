"""Execute bounded checks in the registered worktree and retain a bounded output tail."""

from dataclasses import dataclass
from enum import StrEnum
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from verification_output import first_error, summarize
from verification_selection import Invocation


OUTPUT_LIMIT_BYTES = 1024 * 1024


class Status(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class Result:
    status: Status
    summary: str
    output: str = ""

    @property
    def failed(self) -> bool:
        return self.status not in {Status.PASSED, Status.SKIPPED}


def execute(invocation: Invocation, root: Path, budget: float) -> Result:
    """A process group prevents timeout survivors from changing a later snapshot."""
    started = time.monotonic()
    environment = dict(os.environ)
    if invocation.label not in {"bats", "pytest", "rust"}:
        environment["CI"] = "1"
    try:
        with subprocess.Popen(
            invocation.arguments,
            cwd=root,
            env=environment,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ) as process:
            output, timed_out = collect(process, max(0.01, budget))
            status = Status.TIMEOUT if timed_out else Status.FAILED if process.returncode else Status.PASSED
    except OSError as error:
        return Result(Status.UNAVAILABLE, f"{invocation.label}: unavailable · {error}", str(error))
    evidence = summarize(invocation.label, output)
    if status == Status.PASSED and evidence.executed == 0:
        related_empty = invocation.label == "vitest" and invocation.scope.endswith(" changed files")
        status = Status.SKIPPED if related_empty and "No test files found" in output else Status.UNAVAILABLE
        output = "No tests executed; selected tests were absent or all skipped.\n" + output
    if status == Status.TIMEOUT:
        output = f"timed out after {budget:g}s\n" + output
    summary = (
        f"{invocation.label}: {evidence.summary} · {invocation.scope} · {status} · {time.monotonic() - started:.1f}s"
    )
    if status not in {Status.PASSED, Status.SKIPPED}:
        summary += f"\nError: {first_error(output)}"
    return Result(status, summary, output)


def collect(process: subprocess.Popen[bytes], budget: float) -> tuple[str, bool]:
    tail = bytearray()
    assert process.stdout is not None
    stream = process.stdout

    def drain() -> None:
        while chunk := os.read(stream.fileno(), 65536):
            tail.extend(chunk)
            if len(tail) > OUTPUT_LIMIT_BYTES:
                del tail[:-OUTPUT_LIMIT_BYTES]

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    timed_out = False
    try:
        process.wait(timeout=budget)
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        reader.join(timeout=2)
    return tail.decode("utf-8", errors="replace"), timed_out
