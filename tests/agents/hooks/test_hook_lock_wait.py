"""Native hook entries tolerate brief contention without losing session state."""

from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tests.agents.hooks.herdr_runtime import CREATE, created, hook

import herdr_ownership
import session_store as store


def start_hook(
    event: str, payload: dict, waiting: Path, *, wait_seconds: float | None = None
) -> subprocess.Popen[str]:
    # Observe real flock contention in the child before releasing the parent's lock.
    script = """
import fcntl
from pathlib import Path
import runpy
import sys
sys.path.insert(0, str(Path(sys.argv[1]).parent / 'lib'))
import session_store
if sys.argv[4]:
    session_store.LOCK_WAIT_SECONDS = float(sys.argv[4])
flock = fcntl.flock
waiting = Path(sys.argv[3])
def observed_flock(stream, operation):
    try:
        return flock(stream, operation)
    except BlockingIOError:
        waiting.touch()
        raise
fcntl.flock = observed_flock
sys.argv = [sys.argv[1], 'codex', sys.argv[2]]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            script,
            str(hook),
            event,
            str(waiting),
            "" if wait_seconds is None else str(wait_seconds),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload))
    process.stdin.close()
    process.stdin = None
    return process


def wait_for_contention(markers: list[Path]) -> None:
    deadline = time.monotonic() + 5
    while not all(path.exists() for path in markers):
        assert time.monotonic() < deadline, "Hooks did not reach the held lock"
        time.sleep(0.001)


@pytest.mark.parametrize("event", ["pre-tool-use", "post-agent", "post-workspace", "session-start", "resume"])
def test_concurrent_hook_entries_wait_and_preserve_results(repository: Path, tmp_path: Path, event: str) -> None:
    record = store.register(repository, "codex", "session")
    lock_path = record.directory.parent / ".register.lock" if event == "session-start" else record.directory / ".lock"
    count = 4 if event == "pre-tool-use" else 2
    markers = [tmp_path / f"waiting-{index}" for index in range(count)]
    native_event = "post-tool-use" if event.startswith("post-") else "session-start" if event == "resume" else event
    payloads = [hook_payload(repository, event, index) for index in range(count)]
    with ExitStack() as children:
        with store.file_lock(lock_path):
            processes = [
                children.enter_context(start_hook(native_event, payload, marker))
                for payload, marker in zip(payloads, markers, strict=True)
            ]
            wait_for_contention(markers)
        outputs = [hook_output(process) for process in processes]
    for output in outputs:
        if event in {"session-start", "resume"}:
            assert "additionalContext" in output["hookSpecificOutput"], output
        else:
            assert output == {}, output
    if event.startswith("post-"):
        key = "workspaces" if event == "post-workspace" else "agents"
        expected = {f"w{index}" if key == "workspaces" else f"lane-{index}" for index in range(count)}
        assert set(herdr_ownership.entries(record, key)) == expected


def hook_payload(repository: Path, event: str, index: int) -> dict:
    payload = {"cwd": str(repository), "session_id": "session"}
    if event == "session-start":
        return {**payload, "session_id": f"new-{index}", "source": "startup"}
    if event == "resume":
        return {**payload, "source": "resume"}
    if not event.startswith("post-"):
        return payload
    command, response = successful_result(event, index)
    return {**payload, "tool_name": "Bash", "tool_input": {"command": command}, "tool_response": {"stdout": response}}


def successful_result(event: str, index: int) -> tuple[str, str]:
    if event == "post-workspace":
        return CREATE, created(f"w{index}")
    command = f"herdr agent start lane-{index} --kind claude --pane w{index}:p1"
    agent = {
        "name": f"lane-{index}",
        "terminal_id": f"term_{index}",
        "pane_id": "p1",
        "workspace_id": f"w{index}",
        "agent_session": {"value": f"session_{index}"},
    }
    return command, json.dumps({"result": {"type": "agent_started", "agent": agent}})


def hook_output(process: subprocess.Popen[str]) -> dict:
    try:
        stdout, stderr = process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    assert process.returncode == 0, stderr
    return json.loads(stdout)


@pytest.mark.parametrize("event", ["pre-tool-use", "session-end", "session-start", "resume", "gc"])
def test_hook_reports_the_lock_held_past_the_wait_limit(repository: Path, tmp_path: Path, event: str) -> None:
    record = store.register(repository, "codex", "session")
    lock_path = record.directory / ".lock"
    payload = {"cwd": str(repository), "session_id": "session"}
    native_event = event
    if event == "session-start":
        lock_path = record.directory.parent / ".register.lock"
        payload.update(session_id="new", source="startup")
    elif event == "resume":
        native_event = "session-start"
        payload["source"] = "resume"
    elif event == "gc":
        native_event = "session-end"
        lock_path = store.state_directory() / ".gc.lock"
    with (
        store.file_lock(lock_path),
        start_hook(native_event, payload, tmp_path / "waiting", wait_seconds=0.05) as process,
    ):
        output = hook_output(process)
    message = (
        output["hookSpecificOutput"]["permissionDecisionReason"]
        if event == "pre-tool-use"
        else output["systemMessage"]
    )
    assert str(lock_path) in message
    assert "another hook holds it" in message
    assert "Timed out" in message
    assert "Errno" not in message
    if event == "pre-tool-use":
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
