"""Execute planned quality steps and return bounded diagnostics."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile

from lib.formatter_policy import Step, plan
from lib import process_runner


@dataclass(frozen=True, slots=True)
class LintTarget:
    """An existing file and the quality language that checks it."""

    language: str
    path: Path


def origin(step: Step, path: Path) -> str:
    """Name the step and target a diagnostic belongs to."""
    return f"{step.label} · {path}"


def failure(source: str, status: int, output: str) -> str:
    """Describe a failed command even when it produced no diagnostic output."""
    return f"Lint/format failed\n{source} · exit {status}\nError: {output.strip() or 'No diagnostic output.'}"


def diagnostic_text(data: bytes, truncated: bool) -> str:
    """Decode bounded process output and preserve whether bytes were discarded."""
    value = data.decode(errors="replace").rstrip()
    if truncated:
        value = f"{value}\n[process output truncated]" if value else "[process output truncated]"
    return value


def replace_formatted_file(path: Path, contents: bytes) -> None:
    """Atomically replace formatted content in the same filesystem, preserving permissions."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
        temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_step(step: Step, path: Path) -> str:
    """Run a quality step and return only failures or explicitly meaningful warnings."""
    environment = dict(os.environ)
    if step.writes_stdout:
        environment["PRETTIERD_DEFAULT_CONFIG"] = str(Path.home() / ".prettierrc")
    result = process_runner.run_process(step, path, environment)
    diagnostics = diagnostic_text(result.diagnostics, result.output_truncated)
    if result.timed_out:
        return (
            f"Lint/format timeout\n{step.label} · {path} · after {process_runner.STEP_TIMEOUT_SECONDS:g}s\n"
            f"Error: {diagnostics or 'Process exceeded its time limit.'}"
        )
    if result.returncode:
        return failure(origin(step, path), result.returncode, diagnostics)
    if step.writes_stdout:
        if result.formatted_output_truncated:
            return failure(
                origin(step, path),
                result.returncode,
                f"Formatted output exceeded {process_runner.FORMATTED_OUTPUT_LIMIT_BYTES} bytes.",
            )
        replace_formatted_file(path, result.stdout)
    if step.reports_warnings and diagnostics:
        return f"Lint/format failed\n{step.label} · {path} · exit 0\nDiagnostics: {diagnostics}"
    return ""


def check_file(kind: str, path: Path, readonly: bool = False) -> tuple[str, ...]:
    """Collect quality diagnostics, stopping when a required executable is unavailable."""
    messages: list[str] = []
    for step in plan(kind, path, readonly=readonly):
        if step.policy_error:
            messages.append(f"Lint/format unavailable\n{step.label} · {path}\nReason: {step.policy_error}")
            break
        if step.note:
            messages.append(f"Lint/format skipped\n{step.label} · {path}\nReason: {step.note}")
            continue
        executable = step.arguments[0]
        if shutil.which(executable) is None:
            messages.append(f"Lint/format unavailable\n{executable} · {path}\nReason: {executable} not found in PATH.")
            break
        try:
            message = run_step(step, path)
        except OSError as error:
            message = failure(origin(step, path), 1, str(error))
        if message:
            messages.append(message)
    return tuple(messages)


def supported_targets(
    paths: Iterable[Path], extensions: dict[str, str], kind: str | None = None
) -> tuple[LintTarget, ...]:
    """Pair existing files with their quality language, optionally restricted to one language."""
    targets: list[LintTarget] = []
    for path in paths:
        language = extensions.get(path.suffix.lower())
        if language is None or (kind is not None and language != kind) or not path.is_file():
            continue
        targets.append(LintTarget(language, path))
    return tuple(targets)


def diagnostics(
    targets: Iterable[LintTarget], checker: Callable[[str, Path], tuple[str, ...]] = check_file
) -> tuple[str, ...]:
    """Run checks for supported targets selected from one normalized hook payload."""
    return tuple(message for target in targets for message in checker(target.language, target.path))
