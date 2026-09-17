"""Verify session changes and replace each check's latest receipt atomically."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import time

from session_checks import Status, execute
from session_snapshot import Snapshot, capture
from session_store import Run, StateError, prune
import verification_selection


HOOK_ROOT = Path(__file__).resolve().parent.parent
GATE_BUDGET_SECONDS = 540


def stop(run: Run, *, force: bool = False) -> dict[str, str]:
    """Serialize Stop/check calls so concurrent delivery cannot run a check twice."""
    with run.lock():
        run.touch()
        result = verify(run, force=force)
    prune()
    return result


def verify(run: Run, *, force: bool) -> dict[str, str]:
    started = time.monotonic()
    current = capture(run.root)
    state = run.results()
    full = state.get("revalidate_all", False)
    changed = tuple(path for path, _ in current.entries) if full else run.baseline.changed_paths(current)
    if not changed and not full:
        return record_skip(run, state, "no changes since session registration")
    try:
        rules = verification_selection.load_defaults(HOOK_ROOT / "rules/related_test_defaults.json")
        invocations, errors = verification_selection.language_plan(run.root, rules, changed)
    except (OSError, ValueError, TypeError) as error:
        return configuration_failure(run, state, current.digest, str(error))
    if errors:
        return configuration_failure(run, state, current.digest, "\n".join(errors))
    if not invocations:
        return record_skip(run, state, "no related test runner matched changed paths")
    receipts: dict[str, dict] = {}
    lines: list[str] = []
    failed = new_failure = executed = passed = False
    inputs = verification_inputs(current)
    for invocation in invocations:
        check_id = hashlib.sha256(json.dumps(invocation.arguments).encode()).hexdigest()
        identity = check_identity(inputs, invocation)
        previous = state["checks"].get(check_id)
        if not force and valid_receipt(previous, identity):
            receipt = previous
        else:
            budget = min(check_budget(), max(0.01, GATE_BUDGET_SECONDS - (time.monotonic() - started)))
            result = execute(invocation, run.root, budget)
            receipt = {"input": identity, "status": str(result.status), "summary": bounded_summary(result.summary)}
            if result.failed:
                log = f"cwd: {run.root}\ncommand: {shlex.join(invocation.arguments)}\n\n{result.output}"
                receipt["log"] = str(run.write_log(check_id, log))
            executed = True
            new_failure |= result.failed
        receipts[check_id] = receipt
        passed |= receipt["status"] == Status.PASSED
        failed |= receipt["status"] not in {Status.PASSED, Status.SKIPPED}
        lines.append(receipt["summary"])
        if log := receipt.get("log"):
            lines.append(f"Details: {log}" if Path(log).is_file() else "Details: unavailable (expired)")
    if capture(run.root).digest != current.digest or verification_inputs(current) != inputs:
        state["checks"] = {}
        run.save_results(state)
        return {
            "decision": "block",
            "reason": "Verification unresolved · inputs changed during verification; retry required",
        }
    state.update(checks=receipts, revalidate_all=False)
    state.pop("configuration_failure", None)
    run.save_results(state)
    if failed:
        message = "Verification failed" if new_failure else "Verification unresolved · unchanged; not rerun"
        return notification("\n".join([message, *lines]), block=new_failure)
    outcome = "passed" if passed else "skipped"
    message = (
        f"Verification {outcome} · total {time.monotonic() - started:.1f}s"
        if executed
        else f"Verification reused · {outcome} · unchanged"
    )
    return {"systemMessage": "\n".join([message, *lines])}


def record_skip(run: Run, state: dict, reason: str) -> dict[str, str]:
    state.update(checks={}, revalidate_all=False)
    state.pop("configuration_failure", None)
    run.save_results(state)
    return {"systemMessage": f"Verification skipped · {reason}"}


def bounded_summary(summary: str) -> str:
    if len(summary) <= 2048:
        return summary
    return summary[:1000] + "\n[summary truncated]\n" + summary[-1000:]


def valid_receipt(value: object, identity: str) -> bool:
    if value is None:
        return False
    if (
        not isinstance(value, dict)
        or value.get("status") not in set(Status)
        or not isinstance(value.get("summary"), str)
    ):
        raise StateError("Malformed check receipt; verification cannot be reused")
    return value.get("input") == identity


def unresolved(run: Run) -> bool:
    state = run.results()
    return bool(state.get("configuration_failure") or state.get("revalidate_all")) or any(
        record.get("status") not in {Status.PASSED, Status.SKIPPED} for record in state["checks"].values()
    )


def verification_inputs(snapshot: Snapshot) -> str:
    """Include test configuration, hook implementation, and execution environment."""
    digest = hashlib.sha256(snapshot.digest.encode())
    for path in sorted(HOOK_ROOT.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".json"}:
            digest.update(os.fsencode(path.relative_to(HOOK_ROOT)))
            digest.update(path.read_bytes())
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        in {
            "PATH",
            "VIRTUAL_ENV",
            "UV_PROJECT_ENVIRONMENT",
            "PYTEST_ADDOPTS",
            "RUSTFLAGS",
            "CARGO_BUILD_TARGET",
            "NODE_OPTIONS",
        }
        or key.startswith("RUN_RELATED_TESTS_")
    }
    digest.update(json.dumps(environment, sort_keys=True).encode())
    return digest.hexdigest()


def check_identity(inputs: str, invocation: verification_selection.Invocation) -> str:
    executable = shutil.which(invocation.arguments[0])
    metadata = None
    if executable:
        path = Path(executable).resolve()
        stat = path.stat()
        metadata = (str(path), stat.st_mtime_ns, stat.st_size)
    return hashlib.sha256(json.dumps((inputs, invocation.arguments, metadata)).encode()).hexdigest()


def check_budget() -> float:
    value = float(os.environ.get("RUN_RELATED_TESTS_TIMEOUT_SECONDS", "300"))
    if not 0 < value <= GATE_BUDGET_SECONDS:
        raise StateError(f"Test timeout must be between 0 and {GATE_BUDGET_SECONDS} seconds")
    return value


def configuration_failure(run: Run, state: dict, identity: str, error: str) -> dict[str, str]:
    failure = hashlib.sha256((identity + error).encode()).hexdigest()
    repeated = state.get("configuration_failure") == failure
    state["configuration_failure"] = failure
    run.save_results(state)
    return notification(f"Verification unresolved · invalid test configuration\n{error}", block=not repeated)


def notification(message: str, *, block: bool) -> dict[str, str]:
    return {"decision": "block", "reason": message} if block else {"systemMessage": message}
