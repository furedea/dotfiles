#!/usr/bin/env -S python3 -IB
"""Plan and run file quality checks using the provider's existing notification contract."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


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
    """Encode a Claude PostToolUse context without losing multiline diagnostics."""
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}


def failure(label: str, target: str, status: int, output: str) -> str:
    """Describe a failed command even when it produced no diagnostic output."""
    return (
        f"Quality check failed\n{label} · {target} · exit {status}\nError: {output.strip() or 'No diagnostic output.'}"
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
        return f"Quality check failed\n{step.label} · {path} · exit 0\nDiagnostics: {diagnostics}"
    return ""


def check_file(kind: str, path: Path) -> tuple[str, ...]:
    """Collect quality diagnostics, stopping when a required executable is unavailable."""
    messages: list[str] = []
    for step in plan(kind, path):
        executable = step.arguments[0]
        if shutil.which(executable) is None:
            messages.append(
                f"Quality check unavailable\n{executable} · {path}\nReason: {executable} not found in PATH."
            )
            break
        try:
            message = run_step(step, path)
        except OSError as error:
            message = failure(step.label, str(path), 1, str(error))
        if message:
            messages.append(message)
    return tuple(messages)


def main(arguments: list[str]) -> int:
    """Run the selected language's PostToolUse check."""
    if len(arguments) != 1 or arguments[0] in {"--help", "-h"}:
        print("Usage: lint_format.py <language>", file=sys.stderr)
        return 1
    try:
        payload = json.load(sys.stdin)
        filename = payload.get("tool_input", {}).get("file_path")
        if not filename:
            return 0
        path = Path(filename).absolute()
        if not path.is_file():
            print(f"File not found: {filename}", file=sys.stderr)
            return 1
        for message in check_file(arguments[0], path):
            print(json.dumps(context(message), ensure_ascii=False))
    except (ValueError, TypeError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
