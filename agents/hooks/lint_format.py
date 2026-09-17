#!/usr/bin/env -S python3 -IB
"""Run quality checks for files reported by Claude Code or Codex hooks."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tomllib
from typing import BinaryIO


SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(SCRIPT.parent / "lib"))

import patch_input


EXTENSIONS = {
    ".py": "py",
    ".sh": "sh",
    ".js": "js",
    ".ts": "js",
    ".jsx": "js",
    ".tsx": "js",
    ".rs": "rs",
    ".nix": "nix",
    ".md": "md",
    ".markdown": "md",
    ".json": "json_toml",
    ".toml": "json_toml",
    ".yml": "gha",
    ".yaml": "gha",
    ".txt": "txt",
    ".lua": "lua",
    ".tex": "tex",
    ".bib": "tex",
    ".cls": "tex",
    ".sty": "tex",
}
EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch"})
LANGUAGES = frozenset(EXTENSIONS.values())
PYTHON_TOOL_NAMES = frozenset({"black", "autopep8", "blue", "yapf"})
DPRINT_CONFIG_NAMES = ("dprint.json", "dprint.jsonc", ".dprint.json", ".dprint.jsonc")
OTHER_FORMATTER_CONFIG_NAMES = (
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    "prettier.config.js",
    "prettier.config.cjs",
    "biome.json",
    "biome.jsonc",
)
STEP_TIMEOUT_SECONDS = 60.0
PROCESS_OUTPUT_LIMIT_BYTES = 64 * 1024
FORMATTED_OUTPUT_LIMIT_BYTES = 8 * 1024 * 1024
NOTIFICATION_LIMIT_BYTES = 16 * 1024
MAX_DIAGNOSTICS = 16
READ_CHUNK_BYTES = 8192


@dataclass(frozen=True, slots=True)
class Step:
    """One quality command, including its working directory and output semantics."""

    label: str
    arguments: tuple[str, ...]
    cwd: Path | None = None
    writes_stdout: bool = False
    reports_warnings: bool = False
    policy_error: str | None = None


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
        threads.append(threading.Thread(target=_drain, args=(process.stderr, diagnostics_capture), daemon=True))  # type: ignore[arg-type]
        threads.append(threading.Thread(target=_send_input, args=(process.stdin, path), daemon=True))  # type: ignore[arg-type]
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


def project_root(start: Path, markers: tuple[str, ...]) -> Path | None:
    """Find the nearest ancestor containing one of the project markers."""
    return next(
        (
            directory
            for directory in (start, *start.parents)
            if any((directory / marker).is_file() for marker in markers)
        ),
        None,
    )


def project_files(start: Path, names: tuple[str, ...]) -> tuple[Path, ...]:
    """Return formatter declarations from the nearest ancestor that has any."""
    for directory in (start, *start.parents):
        found = tuple(directory / name for name in names if (directory / name).is_file())
        if found:
            return found
    return ()


def toml_data(path: Path) -> dict | None:
    """Read a project TOML file without turning malformed configuration into a fallback."""
    try:
        with path.open("rb") as stream:
            value = tomllib.load(stream)
    except OSError, tomllib.TOMLDecodeError:
        return None
    return value if isinstance(value, dict) else {}


def dependency_names(data: dict) -> set[str]:
    """Collect normalized dependency names from common PEP 621 and uv tables."""
    values: list[object] = []
    project = data.get("project")
    if isinstance(project, dict):
        values.append(project.get("dependencies"))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            values.extend(optional.values())
    groups = data.get("dependency-groups")
    if isinstance(groups, dict):
        values.extend(groups.values())
    names: set[str] = set()
    for group in values:
        if isinstance(group, list):
            for requirement in group:
                if isinstance(requirement, str):
                    names.add(re.split(r"[<=>!~\[]", requirement, maxsplit=1)[0].strip().lower().replace("-", "_"))
    return names


def python_project_tool(root: Path) -> str | None:
    """Return the declared Python formatter, or None when the project is ambiguous."""
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = toml_data(pyproject)
        if data is None:
            return "invalid pyproject.toml"
        tools_value = data.get("tool")
        tools: dict[str, object] = dict(tools_value) if isinstance(tools_value, dict) else {}
        dependencies = dependency_names(data)
        alternatives = sorted(name for name in PYTHON_TOOL_NAMES if name in tools)
        has_ruff = "ruff" in tools or "ruff" in dependencies
        if has_ruff and alternatives:
            return f"multiple formatters ({', '.join(['ruff', *alternatives])})"
        if has_ruff:
            return "ruff"
        if alternatives:
            return alternatives[0]
    lock = root / "uv.lock"
    if lock.is_file() and 'name = "ruff"' in lock.read_text(errors="replace"):
        return "ruff"
    return None


def policy_step(path: Path, reason: str, cwd: Path | None = None) -> Step:
    """Represent a project selection decision that must be shown instead of silently skipped."""
    return Step("formatter selection", (), cwd, policy_error=f"{reason} Personal defaults were not used for {path}.")


def plan(kind: str, path: Path) -> tuple[Step, ...]:
    """Choose the existing quality tools without running any of them."""
    filename = str(path)
    if kind == "py":
        root = project_root(path.parent, ("pyproject.toml", "uv.lock"))
        if root:
            tool = python_project_tool(root)
            if tool != "ruff":
                declared = tool or "an unknown formatter"
                return (
                    policy_step(
                        path,
                        f"Project {root.name} declares {declared}; automatic ruff selection is unsafe.",
                        root,
                    ),
                )
        prefix = ("uv", "run", "--frozen", "ruff") if root else ("ruff",)
        return (
            Step("ruff format", (*prefix, "format", filename), root),
            Step("ruff fix", (*prefix, "check", "--fix-only", "--quiet", filename), root),
            Step("ruff lint", (*prefix, "check", "--output-format=concise", "--quiet", filename), root),
        )
    if kind == "json_toml":
        declarations = project_files(path.parent, DPRINT_CONFIG_NAMES + OTHER_FORMATTER_CONFIG_NAMES)
        dprint = tuple(item for item in declarations if item.name in DPRINT_CONFIG_NAMES)
        alternatives = tuple(item for item in declarations if item.name in OTHER_FORMATTER_CONFIG_NAMES)
        if alternatives:
            names = ", ".join(item.name for item in alternatives)
            reason = (
                f"Project formatter declarations {names} conflict with dprint."
                if dprint
                else f"Project formatter declaration {names} takes precedence over dprint."
            )
            return (policy_step(path, reason),)
        project_config = dprint[0] if dprint else None
        config = project_config or Path.home() / "dprint.json"
        root = project_config.parent if project_config else path.parent
        relative = str(path.relative_to(root)) if project_config else path.name
        arguments = (
            "--config",
            str(config),
            "--includes-override",
            relative,
            "--allow-no-files",
        )
        return (
            Step("dprint format", ("dprint", "fmt", *arguments), root),
            Step("dprint lint", ("dprint", "check", *arguments), root),
        )
    if kind == "lua":
        root = project_root(path.parent, ("selene.toml",)) or path.parent
        return (Step("stylua format", ("stylua", filename)), Step("selene lint", ("selene", filename), root))
    if kind == "tex":
        steps = (Step("tex-fmt format", ("tex-fmt", filename)),)
        if path.suffix != ".bib":
            steps += (Step("chktex lint", ("chktex", "-q", "-n22", "-n30", filename), reports_warnings=True),)
        return steps
    if kind == "md":
        return (
            Step("autocorrect format", ("autocorrect", "--fix", filename)),
            Step("prettierd format", ("prettierd", filename), writes_stdout=True),
        )
    if kind == "gha":
        if ".github/workflows/" not in filename or path.suffix not in {".yml", ".yaml"}:
            return ()
        return (Step("actionlint lint", ("actionlint", "-oneline", filename)),)
    commands = {
        "rs": (("rustfmt format", "rustfmt"),),
        "txt": (("autocorrect format", "autocorrect", "--fix"),),
        "sh": (("shfmt format", "shfmt", "-w"), ("shellcheck lint", "shellcheck", "-x", "-P", "SCRIPTDIR")),
        "js": (
            ("oxfmt format", "oxfmt", "--write"),
            ("oxlint fix", "oxlint", "--fix"),
            ("oxlint lint", "oxlint", "--deny-warnings"),
        ),
        "nix": (
            ("nixfmt format", "nixfmt"),
            ("statix fix", "statix", "fix"),
            ("statix lint", "statix", "check"),
            ("deadnix lint", "deadnix", "--fail"),
        ),
    }
    if kind not in commands:
        raise ValueError(f"Unknown quality language: {kind}")
    return tuple(Step(label, (*arguments, filename)) for label, *arguments in commands[kind])


def context(message: str) -> dict[str, object]:
    """Encode one provider-compatible PostToolUse context object."""
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}


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
    result = run_process(step, path, environment)
    diagnostics = diagnostic_text(result.diagnostics, result.output_truncated)
    if result.timed_out:
        return (
            f"Lint/format timeout\n{step.label} · {path} · after {STEP_TIMEOUT_SECONDS:g}s\n"
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
                f"Formatted output exceeded {FORMATTED_OUTPUT_LIMIT_BYTES} bytes.",
            )
        replace_formatted_file(path, result.stdout)
    if step.reports_warnings and diagnostics:
        return f"Lint/format failed\n{step.label} · {path} · exit 0\nDiagnostics: {diagnostics}"
    return ""


def check_file(kind: str, path: Path) -> tuple[str, ...]:
    """Collect quality diagnostics, stopping when a required executable is unavailable."""
    messages: list[str] = []
    for step in plan(kind, path):
        if step.policy_error:
            messages.append(f"Lint/format unavailable\n{step.label} · {path}\nReason: {step.policy_error}")
            break
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


def _cwd(payload: dict) -> Path:
    value = payload.get("cwd")
    if not isinstance(value, str) or not value:
        return Path.cwd().resolve()
    return Path(value).expanduser().resolve()


def _input_names(payload: dict) -> tuple[str, ...]:
    values = payload.get("tool_input")
    if not isinstance(values, dict):
        return ()
    tool = payload.get("tool_name")
    command = values.get("command")
    if isinstance(command, str) and (tool == "apply_patch" or not tool):
        return patch_input.paths(command)
    if tool not in EDIT_TOOLS and tool:
        return ()
    names: list[str] = []
    file_path = values.get("file_path") or values.get("path")
    if isinstance(file_path, str):
        names.append(file_path)
    edits = values.get("edits")
    if isinstance(edits, list):
        names.extend(
            item.get("file_path")
            for item in edits
            if isinstance(item, dict) and isinstance(item.get("file_path"), str)
        )
    return tuple(names)


def target_paths(payload: dict) -> tuple[Path, ...]:
    """Resolve provider paths against payload cwd and remove duplicate targets."""
    root = _cwd(payload)
    paths: list[Path] = []
    seen: set[str] = set()
    for name in _input_names(payload):
        path = Path(name).expanduser()
        path = (path if path.is_absolute() else root / path).resolve()
        key = os.path.normcase(os.fspath(path))
        if key not in seen:
            seen.add(key)
            paths.append(path)
    return tuple(paths)


def diagnostics(payload: dict, kind: str | None = None) -> tuple[str, ...]:
    """Run checks for existing supported targets selected from one hook payload."""
    if not isinstance(payload, dict):
        raise TypeError("hook payload must be an object")
    messages: list[str] = []
    for path in target_paths(payload):
        language = EXTENSIONS.get(path.suffix.lower())
        if language is None or (kind is not None and language != kind) or not path.is_file():
            continue
        messages.extend(check_file(language, path))
    return tuple(messages)


def emit(messages: tuple[str, ...]) -> None:
    """Write one structured notification for all diagnostics, or remain silent."""
    if messages:
        selected = list(messages[:MAX_DIAGNOSTICS])
        if len(messages) > MAX_DIAGNOSTICS:
            selected.append(f"[diagnostics truncated: {len(messages) - MAX_DIAGNOSTICS} more]")
        message = "\n\n".join(selected)
        marker = "\n[diagnostics truncated]"
        encoded = message.encode()
        if len(encoded) > NOTIFICATION_LIMIT_BYTES:
            budget = NOTIFICATION_LIMIT_BYTES - len(marker.encode())
            head = budget // 2
            tail = budget - head
            message = encoded[:head].decode(errors="ignore") + marker + encoded[-tail:].decode(errors="ignore")
        print(json.dumps(context(message), ensure_ascii=False))


def main(arguments: list[str]) -> int:
    """Run the dispatcher, with an optional language filter kept for direct compatibility."""
    if len(arguments) > 1 or any(value in {"--help", "-h"} for value in arguments):
        print("Usage: lint_format.py [language]", file=sys.stderr)
        return 1
    kind = arguments[0] if arguments else None
    if kind is not None and kind not in LANGUAGES:
        print("Usage: lint_format.py [language]", file=sys.stderr)
        return 1
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise TypeError("hook payload must be an object")
        values = payload.get("tool_input") or {}
        if kind is not None and isinstance(values, dict) and isinstance(values.get("file_path"), str):
            if not target_paths(payload) or not target_paths(payload)[0].is_file():
                print(f"File not found: {values['file_path']}", file=sys.stderr)
                return 1
        emit(diagnostics(payload, kind))
    except (ValueError, TypeError, OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
