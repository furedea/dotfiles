"""Execute planned quality steps and return bounded diagnostics."""

from collections.abc import Callable, Iterable
import os
from pathlib import Path
import shutil
import tempfile

from lib.formatter_policy import Step, plan
from lib import process_runner


def failure(label: str, target: str, status: int, output: str) -> str:
    """Describe a failed command even when it produced no diagnostic output."""
    return (
        f"Lint/format failed\n{label} · {target} · exit {status}\nError: {output.strip() or 'No diagnostic output.'}"
    )


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
        return failure(step.label, str(path), result.returncode, diagnostics)
    if step.writes_stdout:
        if result.formatted_output_truncated:
            return failure(
                step.label,
                str(path),
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
            message = failure(step.label, str(path), 1, str(error))
        if message:
            messages.append(message)
    return tuple(messages)


def diagnostics(
    paths: Iterable[Path],
    extensions: dict[str, str],
    kind: str | None = None,
    *,
    checker: Callable[[str, Path], tuple[str, ...]] | None = None,
    readonly: bool = False,
) -> tuple[str, ...]:
    """Run checks for existing supported targets selected from one normalized hook payload."""
    messages: list[str] = []
    check = checker or (lambda language, path: check_file(language, path, readonly))
    for path in paths:
        language = extensions.get(path.suffix.lower())
        if language is None or (kind is not None and language != kind) or not path.is_file():
            continue
        messages.extend(check(language, path))
    return tuple(messages)
