"""Verify session changes and replace each check's latest receipt atomically."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import time

from check_execution import Status, execute
from session_snapshot import Snapshot, capture
from session_store import SessionRecord, StateError, prune
import check_selection


HOOK_ROOT = Path(__file__).resolve().parent.parent
GATE_BUDGET_SECONDS = 540


def gate(record: SessionRecord, *, force: bool = False) -> dict[str, str]:
    """Serialize Stop and verify calls so concurrent delivery cannot run a check twice."""
    with record.lock():
        record.touch()
        result = verify(record, force=force)
    prune()
    return result


def verify(record: SessionRecord, *, force: bool) -> dict[str, str]:
    started = time.monotonic()
    current = capture(record.root)
    state = record.results()
    try:
        invocations, skip_reason = selected_checks(record, current, state)
    except (OSError, ValueError, TypeError) as error:
        return configuration_failure(record, state, current.digest, str(error))
    if not invocations:
        return save_skip(record, state, skip_reason)
    receipts: dict[str, dict] = {}
    lines: list[str] = []
    failed = new_failure = executed = passed = False
    inputs = verification_inputs(current)
    for invocation in invocations:
        check_id, identity, previous, reusable = receipt_state(state, inputs, invocation)
        if not force and reusable:
            receipt = previous
        else:
            budget = min(check_budget(), max(0.01, GATE_BUDGET_SECONDS - (time.monotonic() - started)))
            result = execute(invocation, record.root, budget)
            receipt = {
                "input": identity,
                "status": str(result.status),
                "summary": bounded_summary(result.summary),
                "scope": invocation.scope,
            }
            if result.failed:
                log = f"cwd: {record.root}\ncommand: {shlex.join(invocation.arguments)}\n\n{result.output}"
                receipt["log"] = str(record.write_log(check_id, log))
            executed = True
            new_failure |= result.failed
        receipts[check_id] = receipt
        passed |= receipt["status"] == Status.PASSED
        failed |= receipt["status"] not in {Status.PASSED, Status.SKIPPED}
        lines.append(receipt["summary"])
        if log := receipt.get("log"):
            lines.append(f"Details: {log}" if Path(log).is_file() else "Details: unavailable (expired)")
    if capture(record.root).digest != current.digest or verification_inputs(current) != inputs:
        state["checks"] = {}
        record.save_results(state)
        return {
            "decision": "block",
            "reason": "Verification unresolved · inputs changed during verification; retry required",
        }
    state.update(checks=receipts, revalidate_all=False)
    state.pop("configuration_failure", None)
    record.save_results(state)
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


def selected_checks(
    record: SessionRecord, current: Snapshot, state: dict
) -> tuple[list[check_selection.Invocation], str]:
    """Select the same scope for observation and execution without starting checks."""
    full = state.get("revalidate_all", False)
    changed = tuple(path for path, _ in current.entries) if full else record.baseline.changed_paths(current)
    if not changed and not full:
        return [], "no changes since session registration"
    rules = check_selection.load_defaults(HOOK_ROOT / "rules/related_test_defaults.json")
    invocations, errors = check_selection.language_plan(record.root, rules, changed)
    if errors:
        raise StateError("\n".join(errors))
    return invocations, "no related test runner matched changed paths" if not invocations else ""


def receipt_state(state: dict, inputs: str, invocation: check_selection.Invocation) -> tuple[str, str, dict, bool]:
    """Use one fingerprint and receipt validation contract for status and verify."""
    check_id = hashlib.sha256(json.dumps(invocation.arguments).encode()).hexdigest()
    identity = check_identity(inputs, invocation)
    previous = state["checks"].get(check_id)
    reusable = valid_receipt(previous, identity)
    return check_id, identity, previous or {}, reusable


def status(record: SessionRecord) -> dict:
    """Observe receipts and applicability without writes, expiry renewal, or check execution."""
    state = record.results()
    for receipt in state["checks"].values():
        valid_receipt(receipt, "")
    rows = {
        key: {
            "id": key,
            "status": receipt["status"],
            "scope": receipt.get("scope"),
            "summary": bounded_summary(receipt["summary"]),
            "applicability": "unknown",
        }
        for key, receipt in state["checks"].items()
    }
    result = {"worktree": str(record.root), "state": "unknown", "checks": []}
    try:
        current = capture(record.root)
        invocations, skip_reason = selected_checks(record, current, state)
        inputs = verification_inputs(current)
        for row in rows.values():
            row["applicability"] = "not_applicable"
        selected = []
        for invocation in invocations:
            check_id, _, previous, reusable = receipt_state(state, inputs, invocation)
            row = {
                "id": check_id,
                "status": previous.get("status", "not_run"),
                "scope": invocation.scope,
                "summary": bounded_summary(previous.get("summary", "")),
                "applicability": "current" if reusable else "stale" if previous else "not_run",
            }
            rows[check_id] = row
            selected.append(row)
        result["state"] = current_status(selected)
        if skip_reason:
            result["reason"] = skip_reason
        if capture(record.root).digest != current.digest or verification_inputs(current) != inputs:
            raise StateError("Inputs changed during status observation")
        if record.results() != state:
            raise StateError("Verification results changed during status observation")
    except (OSError, ValueError, TypeError) as error:
        result.update(state="unknown", reason=str(error))
        for row in rows.values():
            row["applicability"] = "unknown"
    result["checks"] = list(rows.values())
    return result


def current_status(rows: list[dict]) -> str:
    if not rows:
        return "not_applicable"
    for applicability in ("stale", "not_run"):
        if any(row["applicability"] == applicability for row in rows):
            return applicability
    if any(row["status"] not in {Status.PASSED, Status.SKIPPED} for row in rows):
        return "failed"
    return "passed" if any(row["status"] == Status.PASSED for row in rows) else "skipped"


def save_skip(record: SessionRecord, state: dict, reason: str) -> dict[str, str]:
    state.update(checks={}, revalidate_all=False)
    state.pop("configuration_failure", None)
    record.save_results(state)
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


def unresolved(record: SessionRecord) -> bool:
    state = record.results()
    return bool(state.get("configuration_failure") or state.get("revalidate_all")) or any(
        receipt.get("status") not in {Status.PASSED, Status.SKIPPED} for receipt in state["checks"].values()
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


def check_identity(inputs: str, invocation: check_selection.Invocation) -> str:
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


def configuration_failure(record: SessionRecord, state: dict, identity: str, error: str) -> dict[str, str]:
    failure = hashlib.sha256((identity + error).encode()).hexdigest()
    repeated = state.get("configuration_failure") == failure
    state["configuration_failure"] = failure
    record.save_results(state)
    return notification(f"Verification unresolved · invalid test configuration\n{error}", block=not repeated)


def notification(message: str, *, block: bool) -> dict[str, str]:
    return {"decision": "block", "reason": message} if block else {"systemMessage": message}
