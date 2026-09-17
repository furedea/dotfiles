#!/usr/bin/env -S python3 -IB
"""Run quality checks for files reported by Claude Code or Codex hooks."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


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


@dataclass(frozen=True, slots=True)
class Step:
    """One quality command, including its working directory and output semantics."""

    label: str
    arguments: tuple[str, ...]
    cwd: Path | None = None
    writes_stdout: bool = False
    reports_warnings: bool = False


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


def plan(kind: str, path: Path) -> tuple[Step, ...]:
    """Choose the existing quality tools without running any of them."""
    filename = str(path)
    if kind == "py":
        root = project_root(path.parent, ("pyproject.toml", "uv.lock"))
        prefix = ("uv", "run", "--frozen", "ruff") if root else ("ruff",)
        return (
            Step("ruff format", (*prefix, "format", filename), root),
            Step("ruff fix", (*prefix, "check", "--fix-only", "--quiet", filename), root),
            Step("ruff lint", (*prefix, "check", "--output-format=concise", "--quiet", filename), root),
        )
    if kind == "json_toml":
        arguments = (
            "--config",
            str(Path.home() / "dprint.json"),
            "--includes-override",
            path.name,
            "--allow-no-files",
        )
        return (
            Step("dprint format", ("dprint", "fmt", *arguments), path.parent),
            Step("dprint lint", ("dprint", "check", *arguments), path.parent),
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
    result = subprocess.run(
        step.arguments,
        cwd=step.cwd,
        env=environment,
        input=path.read_bytes() if step.writes_stdout else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if step.writes_stdout else subprocess.STDOUT,
        check=False,
    )
    diagnostics = (result.stderr if step.writes_stdout else result.stdout).decode(errors="replace").rstrip()
    if result.returncode:
        return failure(step.label, str(path), result.returncode, diagnostics)
    if step.writes_stdout:
        replace_formatted_file(path, result.stdout)
    if step.reports_warnings and diagnostics:
        return f"Lint/format failed\n{step.label} · {path} · exit 0\nDiagnostics: {diagnostics}"
    return ""


def check_file(kind: str, path: Path) -> tuple[str, ...]:
    """Collect quality diagnostics, stopping when a required executable is unavailable."""
    messages: list[str] = []
    for step in plan(kind, path):
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
        print(json.dumps(context("\n\n".join(messages)), ensure_ascii=False))


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
