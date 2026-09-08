import json
import os
from pathlib import Path
import shutil
import subprocess

from conftest import REPO_ROOT, load_script_module
import pytest


reuse = load_script_module("agents/hooks/lib/verification_reuse.py", "verification_reuse")


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    (root / "source.txt").write_text("first")
    (root / ".gitignore").write_text("ignored/\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    return root


def test_same_files_have_same_snapshot(repository: Path) -> None:
    assert reuse.repository_digest(repository) == reuse.repository_digest(repository)


@pytest.mark.parametrize("change", ["edit", "add", "delete", "rename", "executable"])
def test_repository_changes_invalidate_snapshot(repository: Path, change: str) -> None:
    before = reuse.repository_digest(repository)
    source = repository / "source.txt"
    if change == "edit":
        source.write_text("second")
    elif change == "add":
        (repository / "new\n file.txt").write_text("new")
    elif change == "delete":
        source.unlink()
    elif change == "rename":
        source.rename(repository / "renamed.txt")
    else:
        source.chmod(0o755)
    assert reuse.repository_digest(repository) != before


def test_ignored_output_does_not_invalidate_snapshot(repository: Path) -> None:
    before = reuse.repository_digest(repository)
    (repository / "ignored").mkdir()
    (repository / "ignored" / "output").write_text("generated")
    assert reuse.repository_digest(repository) == before


def test_symlink_input_disables_reuse(repository: Path) -> None:
    (repository / "link").symlink_to("source.txt")
    with pytest.raises(reuse.UncacheableState):
        reuse.repository_digest(repository)


@pytest.fixture
def gate(tmp_path: Path, repository: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    count = tmp_path / "count"
    hook = hooks / "gate.sh"
    hook.write_text(
        "#!/usr/bin/env bash\n"
        'printf "run\\n" >> "$REUSE_TEST_COUNT"\n'
        'if [ "${REUSE_TEST_CHANGE:-0}" = 1 ]; then printf changed >> source.txt; fi\n'
        'if [ "${REUSE_TEST_FAIL:-0}" = 1 ]; then\n'
        '  printf \'{"decision":"block","reason":"failed: test"}\\n\'\n'
        "else\n"
        "  printf '%s\\n' '{\"systemMessage\":\"Verification passed · total 0.1s\\nBats: 1 passed · 1 file · 0.1s\\nDetails: /tmp/example-log\"}'\n"
        "fi\n"
    )
    monkeypatch.chdir(repository)
    monkeypatch.setenv("REUSE_TEST_COUNT", str(count))
    monkeypatch.setenv("RUN_RELATED_TESTS_BASE_REF", "HEAD")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    # The fake gate does not need a commit, but the snapshot resolves its base.
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        ],
        check=True,
    )
    return hook, count


def invoke(hook: Path, session: str = "test") -> dict:
    result = reuse.run_gate(hook, json.dumps({"session_id": session}).encode())
    assert result.returncode == 0
    return json.loads(result.stdout)


def test_expired_details_do_not_invalidate_an_unresolved_result(tmp_path: Path) -> None:
    reuse.save_record(
        tmp_path / "failure.json",
        {
            "schema": reuse.SCHEMA,
            "id": "same-input",
            "reason": f"Verification failed\nError: assertion failed\nDetails: {tmp_path / 'expired'}",
        },
    )
    result = reuse.previous_notification(tmp_path, "same-input")
    assert result is not None
    message = json.loads(result.stdout)["systemMessage"]
    assert "unresolved" in message
    assert "Error: assertion failed" in message
    assert "Details: unavailable (not retained or expired)" in message


def test_success_is_reused_until_files_change(gate: tuple[Path, Path], repository: Path) -> None:
    hook, count = gate
    invoke(hook)
    reused = invoke(hook)["systemMessage"]
    assert "reused" in reused
    assert reused.splitlines() == ["Verification reused · unchanged", "Bats: 1 passed · 1 file · 0.1s"]
    assert len(count.read_text().splitlines()) == 1
    (repository / "source.txt").write_text("changed")
    invoke(hook)
    assert len(count.read_text().splitlines()) == 2


def test_sessions_do_not_share_success(gate: tuple[Path, Path]) -> None:
    hook, count = gate
    invoke(hook, "one")
    invoke(hook, "two")
    assert len(count.read_text().splitlines()) == 2


def test_unchanged_failure_is_reported_without_blocking_again(
    gate: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook, count = gate
    monkeypatch.setenv("REUSE_TEST_FAIL", "1")
    assert invoke(hook)["decision"] == "block"
    repeated = invoke(hook)
    assert "decision" not in repeated
    assert "unresolved" in repeated["systemMessage"]
    assert "failed: test" in repeated["systemMessage"]
    assert len(count.read_text().splitlines()) == 1


def test_changed_failure_blocks_again(
    gate: tuple[Path, Path],
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook, count = gate
    monkeypatch.setenv("REUSE_TEST_FAIL", "1")
    assert invoke(hook)["decision"] == "block"
    (repository / "source.txt").write_text("attempted fix")
    assert invoke(hook)["decision"] == "block"
    assert len(count.read_text().splitlines()) == 2


def test_forced_failure_blocks_again(gate: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    hook, count = gate
    monkeypatch.setenv("REUSE_TEST_FAIL", "1")
    assert invoke(hook)["decision"] == "block"
    monkeypatch.setenv("RUN_RELATED_TESTS_FORCE", "1")
    assert invoke(hook)["decision"] == "block"
    assert len(count.read_text().splitlines()) == 2


@pytest.mark.parametrize("forced", [False, True])
def test_recovery_replaces_unresolved_failure_with_success(
    gate: tuple[Path, Path],
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    forced: bool,
) -> None:
    hook, count = gate
    monkeypatch.setenv("REUSE_TEST_FAIL", "1")
    assert invoke(hook)["decision"] == "block"
    monkeypatch.delenv("REUSE_TEST_FAIL")
    if forced:
        monkeypatch.setenv("RUN_RELATED_TESTS_FORCE", "1")
    else:
        (repository / "source.txt").write_text("fixed")
    assert "passed" in invoke(hook)["systemMessage"]
    monkeypatch.delenv("RUN_RELATED_TESTS_FORCE", raising=False)
    assert "Verification reused · unchanged" in invoke(hook)["systemMessage"]
    assert len(count.read_text().splitlines()) == 2


def test_failure_notification_is_session_scoped(gate: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    hook, count = gate
    monkeypatch.setenv("REUSE_TEST_FAIL", "1")
    assert invoke(hook, "one")["decision"] == "block"
    assert invoke(hook, "two")["decision"] == "block"
    assert len(count.read_text().splitlines()) == 2


def test_failure_during_changes_is_not_suppressed(gate: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    hook, count = gate
    monkeypatch.setenv("REUSE_TEST_FAIL", "1")
    monkeypatch.setenv("REUSE_TEST_CHANGE", "1")
    assert invoke(hook)["decision"] == "block"
    assert invoke(hook)["decision"] == "block"
    assert len(count.read_text().splitlines()) == 2


@pytest.mark.parametrize("stdout", [b"broken", b"{}", b'{"decision":"block","reason":42}'])
def test_malformed_gate_output_cannot_suppress_future_verification(stdout: bytes) -> None:
    assert reuse.failure_reason(subprocess.CompletedProcess([], 0, stdout, b"")) is None


def test_crashed_gate_cannot_suppress_future_verification() -> None:
    result = subprocess.CompletedProcess([], 1, b'{"decision":"block","reason":"failure"}', b"crash")
    assert reuse.failure_reason(result) is None


def test_forced_failure_invalidates_old_success(gate: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    hook, count = gate
    invoke(hook)
    monkeypatch.setenv("RUN_RELATED_TESTS_FORCE", "1")
    monkeypatch.setenv("REUSE_TEST_FAIL", "1")
    assert invoke(hook)["decision"] == "block"
    monkeypatch.delenv("RUN_RELATED_TESTS_FORCE")
    assert "unresolved" in invoke(hook)["systemMessage"]
    assert len(count.read_text().splitlines()) == 2


def test_forced_uncacheable_run_invalidates_old_success(
    gate: tuple[Path, Path],
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook, count = gate
    invoke(hook)
    link = repository / "link"
    link.symlink_to("source.txt")
    monkeypatch.setenv("RUN_RELATED_TESTS_FORCE", "1")
    monkeypatch.setenv("REUSE_TEST_FAIL", "1")
    invoke(hook)
    link.unlink()
    monkeypatch.delenv("RUN_RELATED_TESTS_FORCE")
    assert invoke(hook)["decision"] == "block"
    assert len(count.read_text().splitlines()) == 3


def test_changes_during_execution_are_not_cached(gate: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    hook, count = gate
    monkeypatch.setenv("REUSE_TEST_CHANGE", "1")
    invoke(hook)
    invoke(hook)
    assert len(count.read_text().splitlines()) == 2


def test_missing_session_runs_without_cache(gate: tuple[Path, Path]) -> None:
    hook, count = gate
    invoke(hook, "")
    invoke(hook, "")
    assert len(count.read_text().splitlines()) == 2


def test_broken_cache_runs_verification(gate: tuple[Path, Path]) -> None:
    hook, count = gate
    invoke(hook)
    for path in Path(os.environ["XDG_CACHE_HOME"]).rglob("result.json"):
        path.write_text("broken")
    invoke(hook)
    assert len(count.read_text().splitlines()) == 2


def test_hook_change_invalidates_success(gate: tuple[Path, Path]) -> None:
    hook, count = gate
    invoke(hook)
    hook.write_text(hook.read_text() + "\n# Changed verification policy\n")
    invoke(hook)
    assert len(count.read_text().splitlines()) == 2


def test_skipped_gate_is_not_successful() -> None:
    result = subprocess.CompletedProcess([], 0, b'{"systemMessage":"Verification skipped before completion."}', b"")
    assert not reuse.successful(result)


@pytest.mark.parametrize("blocked", [False, True])
def test_wrapper_total_replaces_nested_total_without_changing_gate_decision(blocked: bool) -> None:
    field = "reason" if blocked else "systemMessage"
    status = "failed" if blocked else "passed"
    output = {field: f"Verification {status} · total 1.0s\nverification details"}
    if blocked:
        output["decision"] = "block"
    result = subprocess.CompletedProcess([], 0, json.dumps(output).encode(), b"diagnostic")
    timed = reuse.with_total(result, 2.5)
    message = json.loads(timed.stdout)
    assert message[field] == f"Verification {status} · total 2.5s\nverification details"
    assert message.get("decision") == output.get("decision")
    assert timed.stderr == b"diagnostic"


def test_malformed_success_record_runs_verification(gate: tuple[Path, Path]) -> None:
    hook, count = gate
    invoke(hook)
    for path in Path(os.environ["XDG_CACHE_HOME"]).rglob("result.json"):
        path.write_text("[]")
    invoke(hook)
    assert len(count.read_text().splitlines()) == 2


def test_worktrees_do_not_share_cache(repository: Path) -> None:
    assert reuse.cache_directory(repository, "test") != reuse.cache_directory(repository.parent / "other", "test")


@pytest.mark.parametrize(
    ("setting", "override", "expected_reuse"),
    [
        (None, "1", True),
        ('{"enabled":true}', None, True),
        ('{"enabled":true}', "0", False),
        (None, None, False),
        ('{"enabled":false}', None, False),
        ('{"enabled":"true"}', None, False),
        ("broken", None, False),
    ],
)
@pytest.mark.parametrize("helper_missing", [False, True])
def test_shell_entrypoint_reuses_real_gate_selection(
    *,
    gate: tuple[Path, Path],
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    setting: str | None,
    override: str | None,
    expected_reuse: bool,
    helper_missing: bool,
) -> None:
    _, count = gate
    binaries = repository.parent / "bin"
    binaries.mkdir()
    runner = binaries / "bats"
    runner.write_text('#!/usr/bin/env bash\nprintf "run\\n" >> "$REUSE_TEST_COUNT"\n')
    runner.chmod(0o755)
    timeout = binaries / "timeout"
    timeout.write_text('#!/usr/bin/env bash\nshift\n"$@"\n')
    timeout.chmod(0o755)
    (repository / "tests").mkdir()
    (repository / "source.sh").write_text("echo changed\n")
    (repository / "tests" / "source.bats").write_text('@test "example" { true; }\n')
    monkeypatch.setenv("PATH", f"{binaries}:{os.environ['PATH']}")
    monkeypatch.delenv("RUN_RELATED_TESTS_REUSE", raising=False)
    if override is not None:
        monkeypatch.setenv("RUN_RELATED_TESTS_REUSE", override)
    if setting is not None:
        policy = repository / ".agents/hooks/rules/verification_reuse.json"
        policy.parent.mkdir(parents=True)
        policy.write_text(setting)
    hook = REPO_ROOT / "agents/hooks/run_related_tests.sh"
    if helper_missing:
        copied = repository.parent / "incomplete-hooks"
        shutil.copytree(hook.parent, copied)
        (copied / "lib/verification_reuse.py").unlink()
        hook = copied / hook.name
        expected_reuse = False
    command = ["bash", str(hook)]
    payload = b'{"session_id":"entrypoint"}'
    first = subprocess.run(command, input=payload, capture_output=True, check=True)
    assert reuse.successful(first), first.stdout
    second = subprocess.run(command, input=payload, capture_output=True, check=True)
    assert ("reused" in json.loads(second.stdout)["systemMessage"]) == expected_reuse, second.stdout
    assert len(count.read_text().splitlines()) == (1 if expected_reuse else 2)


@pytest.mark.parametrize("explicit", [None, "HEAD", "missing-base"])
def test_base_selection_uses_local_remote_head_without_overriding_explicit_base(
    gate: tuple[Path, Path],
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    explicit: str | None,
) -> None:
    hook = REPO_ROOT / "agents/hooks/run_related_tests.sh"
    subprocess.run(["git", "update-ref", "refs/remotes/origin/trunk", "HEAD"], check=True)
    subprocess.run(["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk"], check=True)
    monkeypatch.setenv("RUN_RELATED_TESTS_REUSE", "0")
    monkeypatch.delenv("RUN_RELATED_TESTS_BASE_REF")
    if explicit is not None:
        monkeypatch.setenv("RUN_RELATED_TESTS_BASE_REF", explicit)
    result = subprocess.run(["bash", str(hook)], input=b"{}", capture_output=True, check=True)
    output = json.loads(result.stdout)
    if explicit == "missing-base":
        assert output["decision"] == "block"
        assert "missing-base" in output["reason"]
    else:
        assert "no changes since" in output["systemMessage"]
        # The cache must resolve exactly the same base as the gate.
        assert reuse.verification_id(repository, hook)


def test_unknown_default_base_is_reported(gate: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    hook = REPO_ROOT / "agents/hooks/run_related_tests.sh"
    monkeypatch.setenv("RUN_RELATED_TESTS_REUSE", "0")
    monkeypatch.delenv("RUN_RELATED_TESTS_BASE_REF")
    result = subprocess.run(["bash", str(hook)], input=b"{}", capture_output=True, check=True)
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    assert "refs/remotes/origin/HEAD" in output["reason"]


@pytest.mark.parametrize(
    ("runner", "runner_output", "exit_code", "summary"),
    [
        ("bats", "1..3\nok 1 good\nnot ok 2 bad\nok 3 optional # skip missing\n", 1, "1 passed, 1 failed, 1 skipped"),
        ("bats", "1..3\nok 1 good\n", 124, "partial results; 3 planned"),
        ("pytest", "... [100%]\n3 passed, 1 skipped in 0.05s\n", 0, "3 passed, 1 skipped"),
        ("pytest", "traceback details\n1 failed, 2 passed in 0.10s\n", 1, "1 failed, 2 passed"),
        ("pytest", "unrecognized output\n", 0, "unavailable"),
    ],
)
def test_reporting_preserves_actual_output_counts_and_failure_status(
    *,
    gate: tuple[Path, Path],
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: str,
    runner_output: str,
    exit_code: int,
    summary: str,
) -> None:
    hook = REPO_ROOT / "agents/hooks/run_related_tests.sh"
    binaries = repository.parent / "report-bin"
    binaries.mkdir()
    executable = binaries / ("uv" if runner == "pytest" else "bats")
    executable.write_text('#!/usr/bin/env bash\nprintf "%s" "$REPORT_TEST_OUTPUT"\nexit "$REPORT_TEST_STATUS"\n')
    executable.chmod(0o755)
    timeout = binaries / "timeout"
    timeout.write_text('#!/usr/bin/env bash\nshift\n"$@"\n')
    timeout.chmod(0o755)
    (repository / "tests").mkdir()
    target = "tests/test_example.py" if runner == "pytest" else "tests/example.bats"
    (repository / target).write_text("# test fixture\n")
    if runner == "pytest":
        (repository / "pyproject.toml").write_text("")
    monkeypatch.setenv("PATH", f"{binaries}:{os.environ['PATH']}")
    monkeypatch.setenv("RUN_RELATED_TESTS_REUSE", "0")
    monkeypatch.setenv("REPORT_TEST_OUTPUT", runner_output)
    monkeypatch.setenv("REPORT_TEST_STATUS", str(exit_code))
    result = subprocess.run(["bash", str(hook)], input=b"{}", capture_output=True, check=True)
    response = json.loads(result.stdout)
    message = response["reason" if exit_code else "systemMessage"]
    assert (response.get("decision") == "block") == bool(exit_code)
    assert summary in message
    assert " · " in message
    assert "· total " in message
    if not exit_code:
        assert "Details:" not in message
        return
    directory = Path(
        next(line.removeprefix("Details: ") for line in message.splitlines() if line.startswith("Details: "))
    )
    assert not directory.is_relative_to(repository)
    assert (directory.stat().st_mode & 0o077) == 0
    details = (directory / "1.output.log").read_text().rstrip()
    assert details.endswith(runner_output.rstrip())
    if exit_code == 124:
        assert details.startswith("timed out after")
    assert ((directory / "1.output.log").stat().st_mode & 0o077) == 0
    assert target in (directory / "1.command.log").read_text()


def test_unavailable_log_storage_does_not_skip_tests(
    gate: tuple[Path, Path],
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Reuse the reporting scenario with an unwritable directory hierarchy.
    blocked = repository.parent / "not-a-directory"
    blocked.write_text("file")
    monkeypatch.setenv("XDG_STATE_HOME", str(blocked))
    hook = REPO_ROOT / "agents/hooks/run_related_tests.sh"
    (repository / "tests").mkdir()
    (repository / "tests" / "example.bats").write_text('@test "actual test" { true; }\n')
    monkeypatch.setenv("RUN_RELATED_TESTS_REUSE", "0")
    result = subprocess.run(["bash", str(hook)], input=b"{}", capture_output=True, check=True)
    message = json.loads(result.stdout)["systemMessage"]
    assert "Bats: 1 passed" in message
    assert "Details:" not in message
