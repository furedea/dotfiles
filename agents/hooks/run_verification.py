#!/usr/bin/env -S python3 -IB
"""Run differential verification while keeping selection, evidence, and retention separate."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time


# This source is deployed as a self-contained hook directory, not as a site package.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "lib"))

import verification_log
import verification_output
import verification_selection

try:
    import verification_reuse
except ModuleNotFoundError as error:
    if error.name != "verification_reuse":
        raise
    verification_reuse = None


@dataclass(slots=True)
class Report:
    """Accumulate evidence and preserve failures independently of successful checks."""

    root: Path
    started: float
    lines: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    passed: bool = False
    failed: bool = False
    directory: Path | None = None
    attempted_logs: bool = False
    records: int = 0

    def append(
        self,
        label: str,
        status: str,
        scope: str,
        *,
        command: str = "",
        output: str = "",
        evidence: str = "",
        duration: float | None = None,
    ) -> None:
        """Add one observed result without treating skipped checks as passes."""
        display = "Bats" if label == "bats" else label
        line = f"{display}: {evidence or status}"
        if scope:
            line += f" · {scope}"
        if evidence and status != "passed":
            line += f" · {status}"
        if duration is not None:
            line += f" · {duration:.1f}s"
        self.lines.append(line)
        if status == "passed":
            self.passed = True
        elif status != "skipped":
            self.failed = True
            self.record_failure(label, status, scope, command=command, output=output, duration=duration)
        if output and status != "passed":
            self.errors.append(f"Error: {display}: {verification_output.first_error(output)}")
            if command:
                self.errors.append(f"Command: {command}")

    def record_failure(
        self, label: str, status: str, scope: str, *, command: str, output: str, duration: float | None
    ) -> None:
        """Persist failure details without turning storage errors into successful evidence."""
        if not self.attempted_logs:
            self.attempted_logs = True
            self.directory = verification_log.prepare_directory(self.root)
        if self.directory is None:
            return
        self.records += 1
        metadata = f"runner: {label}\nstatus: {status}\nscope: {scope}\ncwd: {self.root}\ncommand: {command}\nduration: {duration}\n"
        try:
            verification_log.write_failure(self.directory, self.records, metadata, output)
        except OSError:
            self.directory = None

    def notification(self, skipped_reason: str = "") -> dict[str, str]:
        """Produce the existing provider-neutral Stop notification."""
        elapsed = time.monotonic() - self.started
        if self.failed:
            lines = [
                f"Verification failed · total {elapsed:.1f}s",
                *self.lines,
                *self.errors,
                verification_log.finish(self.directory),
            ]
            return {"decision": "block", "reason": "\n".join(lines)}
        if self.passed:
            return {"systemMessage": "\n".join([f"Verification passed · total {elapsed:.1f}s", *self.lines])}
        reason = skipped_reason or "\n".join(self.lines) or "no related test runner matched changed paths"
        return {"systemMessage": f"Verification skipped · total {elapsed:.1f}s\nReason: {reason}"}


def git_output(*arguments: str) -> str:
    """Read Git output without modifying its configuration or fetching remote state."""
    return subprocess.check_output(["git", *arguments], stderr=subprocess.DEVNULL, text=True).rstrip("\n")


def changed_paths(base: str) -> tuple[str, ...]:
    """Read NUL-delimited paths so spaces, tabs, and newlines remain filenames."""
    outputs = [
        subprocess.check_output(["git", "diff", "--name-only", "-z", base, "--"]),
        subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"]),
    ]
    return tuple(sorted({os.fsdecode(path) for output in outputs for path in output.split(b"\0") if path}))


def timeout_executable() -> str | None:
    """Resolve the configured timeout boundary, preserving explicit overrides."""
    if "RUN_RELATED_TESTS_TIMEOUT_BIN" in os.environ:
        return shutil.which(os.environ["RUN_RELATED_TESTS_TIMEOUT_BIN"])
    for name in ("timeout", "gtimeout"):
        if executable := shutil.which(name):
            return executable
    configured = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "agent-harness/bin/timeout"
    return str(configured) if os.access(configured, os.X_OK) else None


def verify(invocation: verification_selection.Invocation, report: Report) -> None:
    """Run one bounded check and interpret its output using the runner-specific oracle."""
    label, scope, arguments = invocation.label, invocation.scope, invocation.arguments
    command = shlex.join(arguments)
    if shutil.which(arguments[0]) is None:
        report.append(label, "unavailable", scope, command=command, output=f"{arguments[0]} is not available")
        return
    timeout = timeout_executable()
    if timeout is None:
        report.append(label, "unavailable", scope, command=command, output="timeout enforcement is unavailable")
        return
    budget = os.environ.get("RUN_RELATED_TESTS_TIMEOUT_SECONDS", "300" if label in {"bats", "pytest"} else "120")
    started = time.monotonic()
    environment = dict(os.environ)
    if label not in {"bats", "pytest", "rust"}:
        environment["CI"] = "1"
    result = subprocess.run(
        [timeout, budget, *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        env=environment,
        # Interactive test shells must not take ownership of the agent's terminal.
        start_new_session=True,
        check=False,
    )
    duration = time.monotonic() - started
    evidence = verification_output.summarize(label, result.stdout)
    status, output = "passed", ""
    if result.returncode == 124:
        status, output = "timeout", f"timed out after {budget}s\n{result.stdout}"
    elif result.returncode:
        status, output = "failed", result.stdout or f"exited with status {result.returncode}"
    elif evidence.executed == 0:
        if label == "vitest" and scope.endswith(" changed files") and "No test files found" in result.stdout:
            status, output = "skipped", "No related tests executed."
        else:
            status, output = "unavailable", "No tests executed; selected tests were absent or all skipped."
    report.append(label, status, scope, command=command, output=output, evidence=evidence.summary, duration=duration)


def run_gate() -> dict[str, str]:
    """Verify changed paths against the local base reference and configured rules."""
    started = time.monotonic()
    try:
        root = Path(git_output("rev-parse", "--show-toplevel"))
    except OSError, subprocess.CalledProcessError:
        return Report(Path.cwd(), started).notification("not inside a Git repository")
    os.chdir(root)
    report = Report(root, started)
    base_ref = os.environ.get("RUN_RELATED_TESTS_BASE_REF", "refs/remotes/origin/HEAD")
    try:
        base = git_output("merge-base", "HEAD", base_ref)
    except subprocess.CalledProcessError:
        report.append(
            "git",
            "unavailable",
            f"branch base {base_ref}",
            command=shlex.join(("git", "merge-base", "HEAD", base_ref)),
            output="branch base reference is unavailable",
        )
        return report.notification()
    try:
        changed = changed_paths(base)
        if not changed:
            return report.notification(f"no changes since {base_ref}")
        rules = verification_selection.load_defaults(ROOT / "rules/related_test_defaults.json")
        invocations, errors = verification_selection.language_plan(root, rules, changed)
        for error in errors:
            report.append("configuration", "unavailable", "project test rules", output=error)
        for invocation in invocations:
            verify(invocation, report)
    except verification_selection.UnknownTestCommand as error:
        report.append("javascript_typescript", "unavailable", "full suite", output=str(error))
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        report.append("configuration", "unavailable", "verification", output=str(error))
    return report.notification()


def reuse_enabled() -> bool:
    """Require explicit adoption for reuse of stable local verification inputs."""
    if "RUN_RELATED_TESTS_REUSE" in os.environ:
        return os.environ["RUN_RELATED_TESTS_REUSE"] == "1"
    try:
        root = Path(git_output("rev-parse", "--show-toplevel"))
        return json.loads((root / ".agents/hooks/rules/verification_reuse.json").read_text()).get("enabled") is True
    except OSError, ValueError, AttributeError, subprocess.CalledProcessError:
        return False


def main() -> int:
    """Use the existing opt-in cache, otherwise emit fresh verification evidence."""
    if sys.argv[1:]:
        print("Usage: run_verification.py < hook-input.json", file=sys.stderr)
        return 0 if sys.argv[1:] in (["-h"], ["--help"]) else 1
    started = time.time()
    if verification_reuse is not None and reuse_enabled():
        result = verification_reuse.run_gate(Path(__file__), sys.stdin.buffer.read())
        result = verification_reuse.with_total(result, time.time() - started)
        sys.stdout.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
        return result.returncode
    print(json.dumps(run_gate(), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
