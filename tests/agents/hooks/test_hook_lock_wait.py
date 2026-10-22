"""Native hook entries tolerate brief contention without losing session state."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tests.agents.hooks.herdr_runtime import CREATE, created, hook, set_agents

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
import herdr_ownership
if sys.argv[4]:
    session_store.LOCK_WAIT_SECONDS = float(sys.argv[4])
flock = fcntl.flock
waiting = Path(sys.argv[3])
def observed_flock(stream, operation):
    try:
        return flock(stream, operation | (fcntl.LOCK_NB if operation == fcntl.LOCK_EX else 0))
    except BlockingIOError:
        waiting.touch()
        if operation == fcntl.LOCK_EX:
            return flock(stream, operation)
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


@pytest.mark.parametrize("event", ["post-agent", "post-workspace", "session-start", "resume"])
def test_concurrent_hook_entries_wait_and_preserve_results(repository: Path, tmp_path: Path, event: str) -> None:
    record = store.register(repository, "codex", "session")
    lock_path = (
        record.directory.parent / ".register.lock"
        if event == "session-start"
        else record.directory / (".herdr.lock" if event.startswith("post-") else ".lock")
    )
    count = 2
    markers = [tmp_path / f"waiting-{index}" for index in range(count)]
    native_event = "post-tool-use" if event.startswith("post-") else "session-start" if event == "resume" else event
    payloads = [hook_payload(repository, event, index) for index in range(count)]
    with ExitStack() as children:
        with store.file_lock(lock_path):
            processes = [
                children.enter_context(start_hook(native_event, payload, marker, wait_seconds=5))
                for payload, marker in zip(payloads, markers, strict=True)
            ]
            wait_for_contention(markers)
            time.sleep(0.7)
            assert all(process.poll() is None for process in processes)
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
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    assert process.returncode == 0, stderr
    return json.loads(stdout)


@pytest.mark.parametrize("event", ["session-start", "resume", "post-agent"])
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
        record.end(now=1)
        os.utime(record.directory, (1, 1))
    elif event == "post-agent":
        native_event = "post-tool-use"
        lock_path = record.directory / ".herdr.lock"
        payload = hook_payload(repository, event, 0)
    with (
        store.file_lock(lock_path),
        start_hook(native_event, payload, tmp_path / "waiting", wait_seconds=0.5) as process,
    ):
        output = hook_output(process)
    if event == "resume":
        assert "additionalContext" in output["hookSpecificOutput"], output
        assert "systemMessage" not in output
        assert record.results()["ended_at"] == 1
        assert record.directory.stat().st_mtime > 1
        return
    message = output["systemMessage"]
    assert str(lock_path) in message
    assert "another hook holds it" in message
    assert "Timed out" in message
    assert "Errno" not in message


def test_session_end_skips_a_record_locked_past_its_wait_limit(repository: Path, tmp_path: Path) -> None:
    record = store.register(repository, "codex", "session")
    payload = {"cwd": str(repository), "session_id": "session"}
    with (
        record.lock(),
        start_hook("session-end", payload, tmp_path / "waiting") as process,
    ):
        try:
            stdout, stderr = process.communicate(timeout=2.8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            pytest.fail("SessionEnd must finish before Codex's 3-second timeout")
        assert process.returncode == 0, stderr
        assert stderr == ""
        assert json.loads(stdout) == {}
        assert "ended_at" not in record.results()


@pytest.mark.parametrize("event", ["session-start", "session-end", "stop"])
def test_busy_gc_does_not_fail_hooks(repository: Path, tmp_path: Path, event: str) -> None:
    payload = {"cwd": str(repository), "session_id": "session", "source": "startup"}
    with (
        store.file_lock(store.state_directory() / ".gc.lock"),
        start_hook(event, payload, tmp_path / "waiting") as process,
    ):
        output = hook_output(process)
    if event == "session-start":
        assert "additionalContext" in output["hookSpecificOutput"]
        assert "systemMessage" not in output
    elif event == "stop":
        assert "no changes" in output["systemMessage"]
        assert "decision" not in output
    else:
        assert output == {}


def test_tools_keep_herdr_ownership_during_verification(repository: Path, tmp_path: Path, herdr: Path) -> None:
    record = store.register(repository, "codex", "session")
    with record.lock():
        with start_hook("pre-tool-use", hook_payload(repository, "pre-tool-use", 0), tmp_path / "pre") as process:
            assert hook_output(process) == {}
        with start_hook("post-tool-use", hook_payload(repository, "post-agent", 0), tmp_path / "post") as process:
            assert hook_output(process) == {}
        assert set(herdr_ownership.entries(record, "agents")) == {"lane-0"}
        set_agents(herdr, "lane-0 w0 term_0 session_0")
        payload = {
            "cwd": str(repository),
            "session_id": "session",
            "tool_name": "Bash",
            "tool_input": {"command": "herdr agent prompt lane-0 --text hello"},
        }
        with start_hook("pre-tool-use", payload, tmp_path / "prompt") as process:
            assert hook_output(process) == {}


@pytest.mark.parametrize("event", ["stop", "session-end"])
def test_verification_and_session_end_wait_past_the_short_limit(
    verification_record: store.SessionRecord, verification_calls: Path, tmp_path: Path, event: str
) -> None:
    record = verification_record
    (record.root / "source.py").write_text("task edit")
    payload = {"cwd": str(record.root), "session_id": "verification-test"}
    markers = [tmp_path / f"waiting-{index}" for index in range(2 if event == "stop" else 1)]
    with ExitStack() as children:
        with record.lock():
            processes = [children.enter_context(start_hook(event, payload, marker)) for marker in markers]
            wait_for_contention(markers)
            time.sleep(0.7)
            assert all(process.poll() is None for process in processes)
        outputs = [hook_output(process) for process in processes]
    if event == "session-end":
        assert outputs == [{}]
        assert record.results()["ended_at"] > 0
    else:
        assert all("passed" in output["systemMessage"] for output in outputs)
        assert sum("reused" in output["systemMessage"] for output in outputs) == 1
        assert len(verification_calls.read_text().splitlines()) == 1


def test_busy_resume_does_not_block_another_registration(repository: Path, tmp_path: Path) -> None:
    record = store.register(repository, "codex", "session")
    marker = tmp_path / "resuming"
    with ExitStack() as children:
        with record.lock():
            resuming = children.enter_context(
                start_hook("session-start", hook_payload(repository, "resume", 0), marker, wait_seconds=5)
            )
            wait_for_contention([marker])
            process = children.enter_context(
                start_hook("session-start", hook_payload(repository, "session-start", 0), tmp_path / "new")
            )
            assert "additionalContext" in hook_output(process)["hookSpecificOutput"]
        assert "additionalContext" in hook_output(resuming)["hookSpecificOutput"]
