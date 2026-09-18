"""Run quality processes with bounded I/O and a fixed execution deadline."""

from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import tempfile
import threading
from typing import BinaryIO

from lib.formatter_policy import Step


STEP_TIMEOUT_SECONDS = 60.0
PROCESS_OUTPUT_LIMIT_BYTES = 64 * 1024
FORMATTED_OUTPUT_LIMIT_BYTES = 8 * 1024 * 1024
READ_CHUNK_BYTES = 8192


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Bounded output and status from one quality process."""

    returncode: int
    stdout: bytes = b""
    diagnostics: bytes = b""
    timed_out: bool = False
    output_truncated: bool = False
    formatted_output_truncated: bool = False


@dataclass(slots=True)
class _Capture:
    """Drain one pipe while retaining at most its configured byte limit."""

    limit: int
    destination: BinaryIO | None = None
    data: bytearray = field(default_factory=bytearray)
    total: int = 0
    truncated: bool = False

    def append(self, chunk: bytes) -> None:
        retained = self.total
        self.total += len(chunk)
        remaining = self.limit - retained
        if self.destination is not None:
            if remaining > 0:
                self.destination.write(chunk[:remaining])
            if len(chunk) > max(remaining, 0):
                self.truncated = True
            return
        if remaining > 0:
            self.data.extend(chunk[:remaining])
        if len(chunk) > max(remaining, 0):
            self.truncated = True


def _drain(stream: BinaryIO, capture: _Capture) -> None:
    try:
        while chunk := stream.read(READ_CHUNK_BYTES):
            capture.append(chunk)
    except OSError:
        capture.truncated = True


def _send_input(stream: BinaryIO, path: Path) -> None:
    try:
        with path.open("rb") as source:
            while chunk := source.read(READ_CHUNK_BYTES):
                stream.write(chunk)
        stream.close()
    except BrokenPipeError, OSError:
        return


def run_process(step: Step, path: Path, environment: dict[str, str]) -> ProcessResult:
    """Run one process with bounded pipes and a deadline."""
    output_file: BinaryIO | None = tempfile.TemporaryFile() if step.writes_stdout else None
    process = subprocess.Popen(
        step.arguments,
        cwd=step.cwd,
        env=environment,
        stdin=subprocess.PIPE if step.writes_stdout else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if step.writes_stdout else subprocess.STDOUT,
    )
    stdout_capture = _Capture(
        FORMATTED_OUTPUT_LIMIT_BYTES if step.writes_stdout else PROCESS_OUTPUT_LIMIT_BYTES,
        output_file,
    )
    diagnostics_capture = _Capture(PROCESS_OUTPUT_LIMIT_BYTES) if step.writes_stdout else stdout_capture
    threads = [
        threading.Thread(target=_drain, args=(process.stdout, stdout_capture), daemon=True),  # type: ignore[arg-type]
    ]
    if step.writes_stdout:
        threads.append(
            threading.Thread(target=_drain, args=(process.stderr, diagnostics_capture), daemon=True)  # type: ignore[arg-type]
        )
        threads.append(
            threading.Thread(target=_send_input, args=(process.stdin, path), daemon=True)  # type: ignore[arg-type]
        )
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=STEP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait()
    for thread in threads:
        thread.join(timeout=1)
    stdout = b""
    if output_file is not None:
        output_file.seek(0)
        stdout = output_file.read()
        output_file.close()
    return ProcessResult(
        process.returncode if process.returncode is not None else 1,
        stdout,
        bytes(diagnostics_capture.data),
        timed_out,
        diagnostics_capture.truncated,
        stdout_capture.truncated if step.writes_stdout else False,
    )
