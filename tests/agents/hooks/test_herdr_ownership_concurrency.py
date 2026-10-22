"""Overlapping successful results preserve every ownership record in the session."""

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
from threading import Event

import pytest
from pytest_mock import MockerFixture

from tests.agents.hooks.herdr_runtime import CREATE, created

import herdr_ownership
import session_store as store


@pytest.mark.parametrize("kind", ["agent", "workspace"])
def test_overlapping_successful_results_keep_both_records(repository: Path, mocker: MockerFixture, kind: str) -> None:
    record = store.register(repository, "codex", "session")
    first_writing, second_waiting, release_first = Event(), Event(), Event()
    atomic_json, lock = herdr_ownership.atomic_json, herdr_ownership.file_lock

    def pause_first_write(path: Path, value: dict) -> None:
        if not first_writing.is_set():
            first_writing.set()
            assert release_first.wait(5)
        atomic_json(path, value)

    @contextmanager
    def observe_lock(path: Path, *, timeout: float | None = None) -> Generator[None]:
        if first_writing.is_set():
            second_waiting.set()
        with lock(path, timeout=5):
            yield

    def confirm(index: int) -> None:
        if kind == "workspace":
            command, response = CREATE, created(f"w{index}")
        else:
            command = f"herdr agent start lane-{index} --kind claude --pane w{index}:p1"
            agent = {
                "name": f"lane-{index}",
                "terminal_id": f"term_{index}",
                "pane_id": "p1",
                "workspace_id": f"w{index}",
                "agent_session": {"value": f"session_{index}"},
            }
            response = json.dumps({"result": {"type": "agent_started", "agent": agent}})
        herdr_ownership.confirm(record, command, {"stdout": response})
        if index == 2:
            second_waiting.set()

    mocker.patch.object(herdr_ownership, "atomic_json", autospec=True, side_effect=pause_first_write)
    mocker.patch.object(herdr_ownership, "file_lock", autospec=True, side_effect=observe_lock)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(confirm, 1)
        try:
            assert first_writing.wait(5)
            second = executor.submit(confirm, 2)
            assert second_waiting.wait(5)
        finally:
            release_first.set()
        first.result(timeout=5)
        second.result(timeout=5)
    key = "workspaces" if kind == "workspace" else "agents"
    expected = {"w1", "w2"} if kind == "workspace" else {"lane-1", "lane-2"}
    assert set(herdr_ownership.entries(record, key)) == expected
