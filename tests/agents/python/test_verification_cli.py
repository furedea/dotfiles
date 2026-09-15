"""Gate integration with disposable Git state, subprocesses, and runner evidence."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from conftest import CliRunner, REPO_ROOT, StubWriter


SCRIPT = "agents/hooks/run_verification.py"
REAL_BATS = shutil.which("bats")


@pytest.fixture
def gate_project(
    git_project: Path,
    executable: StubWriter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    monkeypatch.setenv("GATE_FIXTURE", str(git_project))
    monkeypatch.setenv("RUN_RELATED_TESTS_BASE_REF", "HEAD")
    monkeypatch.setenv("RUN_RELATED_TESTS_REUSE", "0")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path_factory.mktemp("verification-state")))
    for name in ("RUN_RELATED_TESTS_TIMEOUT_BIN", "RUN_RELATED_TESTS_BATS_BIN", "RUN_RELATED_TESTS_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    executable(
        "timeout",
        """
        import os, sys
        from pathlib import Path
        (Path(os.environ["GATE_FIXTURE"]) / ".git/budget").write_text(sys.argv[1])
        if os.environ.get("TIMEOUT_FIXTURE") == "1":
            sys.exit(124)
        os.execvp(sys.argv[2], sys.argv[2:])
    """,
    )
    for name in ("bats", "uv", "cargo", "pnpm", "npm", "node"):
        executable(
            name,
            """
            import json, os, sys
            from pathlib import Path
            root = Path(os.environ["GATE_FIXTURE"])
            with (root / ".git/runner_calls.jsonl").open("a") as stream:
                stream.write(json.dumps({"tool": Path(sys.argv[0]).name, "args": sys.argv[1:], "ci": os.environ.get("CI")}) + "\\n")
            print(os.environ.get("TEST_RUNNER_OUTPUT", "custom runner finished successfully"))
            sys.exit(int(os.environ.get("TEST_RUNNER_STATUS", "0")))
        """,
        )
    return git_project


def prepare(project: Path, files: dict[str, str], changed: tuple[str, ...] = ()) -> None:
    for name, content in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--quiet", "--allow-empty", "-m", "gate fixture"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    for name in changed:
        path = project / name
        path.write_text(path.read_text() + "\n")


def calls(project: Path) -> list[dict]:
    path = project / ".git/runner_calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def message(result: subprocess.CompletedProcess[str], *, blocked: bool = False) -> str:
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    if blocked:
        assert payload["decision"] == "block"
        assert "Verification passed" not in payload["reason"]
        return payload["reason"]
    assert "decision" not in payload
    return payload["systemMessage"]


@pytest.mark.parametrize("state", ["unstaged", "staged", "committed", "untracked"])
def test_changes_are_revalidated_even_on_continuation(run_cli: CliRunner, gate_project: Path, state: str) -> None:
    files = {"tests/script.bats": "", **({"script.sh": "echo base\n"} if state != "untracked" else {})}
    prepare(gate_project, files)
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=gate_project, check=True, capture_output=True
    )
    (gate_project / "script.sh").write_text("echo changed\n")
    if state in {"staged", "committed"}:
        subprocess.run(["git", "add", "script.sh"], cwd=gate_project, check=True, capture_output=True)
    if state == "committed":
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "changed fixture"], cwd=gate_project, check=True, capture_output=True
        )
    result = run_cli(
        SCRIPT,
        payload={"stop_hook_active": True, "session_id": "test"},
        env={
            "RUN_RELATED_TESTS_BASE_REF": "origin/main",
            "TEST_RUNNER_OUTPUT": f"{state} change was verified",
            "TEST_RUNNER_STATUS": "1",
        },
    )
    assert f"{state} change was verified" in message(result, blocked=True)
    assert calls(gate_project)[0]["args"] == ["tests/script.bats"]


def test_unavailable_branch_base_blocks(run_cli: CliRunner, git_project: Path) -> None:
    result = run_cli(SCRIPT, env={"RUN_RELATED_TESTS_BASE_REF": "origin/missing"})
    assert "git: unavailable · branch base origin/missing" in message(result, blocked=True)


def test_non_git_directory_is_skipped(run_cli: CliRunner) -> None:
    assert "Reason: not inside a Git repository" in message(run_cli(SCRIPT))


@pytest.mark.parametrize(
    "changed,package,reason",
    [
        (None, None, "no changes since HEAD"),
        ("app.js", None, "no related test runner matched changed paths"),
        ("settings.json", {}, "no related test runner matched changed paths"),
    ],
)
def test_skips_without_applicable_changes(
    run_cli: CliRunner, gate_project: Path, changed: str | None, package: dict | None, reason: str
) -> None:
    files = {"package.json": json.dumps(package)} if package is not None else {}
    if changed:
        files[changed] = ""
    prepare(gate_project, files, (changed,) if changed else ())
    assert "Reason: " + reason in message(run_cli(SCRIPT))
    assert not calls(gate_project)


def test_javascript_without_test_command_blocks(run_cli: CliRunner, gate_project: Path) -> None:
    prepare(gate_project, {"package.json": '{"scripts":{}}', "src/app.ts": ""}, ("src/app.ts",))
    text = message(run_cli(SCRIPT), blocked=True)
    assert "javascript_typescript: unavailable · full suite" in text
    assert "test command could not be determined" in text


@pytest.mark.parametrize(
    "override,detail",
    [
        ({"RUN_RELATED_TESTS_BATS_BIN": "missing-bats-runner"}, "missing-bats-runner is not available"),
        ({"RUN_RELATED_TESTS_TIMEOUT_BIN": "missing-timeout-runner"}, "timeout enforcement is unavailable"),
        ({"TIMEOUT_FIXTURE": "1", "RUN_RELATED_TESTS_TIMEOUT_SECONDS": "1"}, "timed out after 1s"),
    ],
)
def test_required_execution_boundaries_fail_closed(
    run_cli: CliRunner, gate_project: Path, override: dict, detail: str
) -> None:
    prepare(gate_project, {"script.sh": "", "tests/script.bats": ""}, ("script.sh",))
    text = message(run_cli(SCRIPT, env=override), blocked=True)
    assert "Bats: " in text and "1 targets" in text
    assert detail in text


def test_home_manager_timeout_resolves_outside_path(
    run_cli: CliRunner, gate_project: Path, executable: StubWriter
) -> None:
    directory = gate_project / "bin"
    configured = gate_project / "home/.config/agent-harness/bin/timeout"
    configured.parent.mkdir(parents=True)
    (directory / "timeout").rename(configured)
    prepare(gate_project, {"script.sh": "", "tests/script.bats": ""}, ("script.sh",))
    executable(
        "git",
        """
        import os, sys
        args = sys.argv[1:]
        if args == ["rev-parse", "--show-toplevel"]:
            print(os.environ["GATE_FIXTURE"])
        elif args == ["merge-base", "HEAD", "HEAD"]:
            print("base")
        elif args == ["diff", "--name-only", "-z", "base", "--"]:
            sys.stdout.buffer.write(b"script.sh\\0")
        elif args != ["ls-files", "--others", "--exclude-standard", "-z"]:
            sys.exit("unexpected git arguments: " + repr(args))
    """,
    )
    result = run_cli(SCRIPT, env={"PATH": str(directory), "XDG_CONFIG_HOME": str(gate_project / "home/.config")})
    assert message(result).startswith("Verification passed")
    assert (gate_project / ".git/budget").read_text() == "300"


@pytest.mark.parametrize("kind,budget", [("bats", "300"), ("pytest", "300"), ("rust", "120"), ("javascript", "120")])
@pytest.mark.parametrize("override", [None, "7"])
def test_timeout_budgets(run_cli: CliRunner, gate_project: Path, kind: str, budget: str, override: str | None) -> None:
    files, changed = {
        "bats": ({"tests/source.bats": ""}, "tests/source.bats"),
        "pytest": ({"pyproject.toml": "", "tests/test_source.py": ""}, "tests/test_source.py"),
        "rust": ({"Cargo.toml": "", "tests/source.rs": ""}, "tests/source.rs"),
        "javascript": (
            {"package.json": '{"scripts":{"test":"node --test"}}', "tests/source.test.js": ""},
            "tests/source.test.js",
        ),
    }[kind]
    prepare(gate_project, files, (changed,))
    result = run_cli(SCRIPT, env={"RUN_RELATED_TESTS_TIMEOUT_SECONDS": override} if override else {})
    assert message(result).startswith("Verification passed")
    assert (gate_project / ".git/budget").read_text() == (override or budget)


def test_failure_summary_is_short_but_saved_output_is_complete(run_cli: CliRunner, gate_project: Path) -> None:
    prepare(gate_project, {"script.sh": "", "tests/script.bats": ""}, ("script.sh",))
    output = "\n".join(f"failure line {index:02d}" for index in range(1, 61))
    text = message(run_cli(SCRIPT, env={"TEST_RUNNER_OUTPUT": output, "TEST_RUNNER_STATUS": "1"}), blocked=True)
    assert "Bats: test count unavailable · 1 targets" in text
    assert "Error: Bats: failure line 01" in text and "failure line 60" not in text
    directory = Path(
        next(line.removeprefix("Details: ") for line in text.splitlines() if line.startswith("Details: "))
    )
    assert any("failure line 60" in path.read_text() for path in directory.iterdir() if path.is_file())


def test_success_has_counts_but_does_not_store_full_logs(run_cli: CliRunner, gate_project: Path) -> None:
    prepare(gate_project, {"tests/example.bats": ""}, ("tests/example.bats",))
    text = message(
        run_cli(
            SCRIPT,
            env={
                "TEST_RUNNER_OUTPUT": "diagnostic before tests\n1..3\nok 1 first\nok 2 second\nok 3 optional # skip unavailable\n"
            },
        )
    )
    assert text.startswith("Verification passed · total ")
    assert "Bats: 2 passed, 1 skipped" in text and "Details:" not in text
    assert not (Path(os.environ["XDG_STATE_HOME"]) / "agent-harness/verification").exists()


@pytest.mark.parametrize(
    "content,files",
    [
        (
            '{"source.py":["tests/test_source.py","tests/test_missing.py"]}',
            {"pyproject.toml": "", "tests/test_source.py": ""},
        ),
        ("{broken", {"pyproject.toml": "", "tests/test_source.py": ""}),
        ('{"source.py":"tests/test_source.py"}', {"pyproject.toml": ""}),
        ('{"source.py":["tests/test_source.py"]}', {"tests/test_source.py": ""}),
        ('{"source.py":["tests/empty"]}', {"tests/empty/README.md": ""}),
    ],
)
def test_incomplete_target_configuration_blocks(
    run_cli: CliRunner, gate_project: Path, content: str, files: dict
) -> None:
    prepare(
        gate_project,
        {"source.py": "", ".agents/hooks/rules/related_test_extensions.json": content, **files},
        ("source.py",),
    )
    assert "configuration" in message(run_cli(SCRIPT), blocked=True)


def test_missing_default_rules_block(run_cli: CliRunner, gate_project: Path) -> None:
    hook = gate_project / "hooks/run_verification.py"
    hook.parent.mkdir()
    shutil.copyfile(REPO_ROOT / SCRIPT, hook)
    shutil.copytree(REPO_ROOT / "agents/hooks/lib", hook.parent / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    prepare(gate_project, {"source.py": "", "pyproject.toml": ""}, ("source.py",))
    assert "related_test_defaults.json" in message(run_cli(str(hook)), blocked=True)


@pytest.mark.parametrize(
    "files,changed,output,expected",
    [
        (
            {
                "Cargo.toml": "",
                "source.rs": "",
                ".agents/hooks/rules/related_test_extensions.json": '{"source.rs":["source.rs"]}',
            },
            "source.rs",
            "test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 12 filtered out; finished in 0.00s",
            "block",
        ),
        ({"pyproject.toml": "", "tests/test_source.py": ""}, "tests/test_source.py", "3 skipped in 0.01s", "block"),
        ({"tests/source.bats": ""}, "tests/source.bats", "1..1\nok 1 source # skip unavailable service", "block"),
        (
            {"Cargo.toml": "", "source.rs": ""},
            "source.rs",
            "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s",
            "passed",
        ),
        (
            {"pyproject.toml": "", "tests/test_source.py": ""},
            "tests/test_source.py",
            "custom runner finished successfully",
            "unknown",
        ),
        (
            {"package.json": '{"packageManager":"pnpm@10","devDependencies":{"vitest":"1"}}'},
            "source.ts",
            "No test files found, exiting with code 0",
            "skipped",
        ),
        (
            {"package.json": '{"packageManager":"pnpm@10","devDependencies":{"vitest":"1"}}'},
            "source.ts",
            "Tests  2 skipped (2)",
            "block",
        ),
    ],
)
def test_runner_output_requires_actual_evidence(
    *, run_cli: CliRunner, gate_project: Path, files: dict, changed: str, output: str, expected: str
) -> None:
    prepare(gate_project, {changed: "", **files}, (changed,))
    text = message(run_cli(SCRIPT, env={"TEST_RUNNER_OUTPUT": output}), blocked=expected == "block")
    if expected == "block":
        assert "No tests executed" in text
    elif expected == "unknown":
        assert "Verification passed" in text and "test count unavailable" in text
    else:
        assert f"Verification {expected}" in text


@pytest.mark.integration
@pytest.mark.skipif(REAL_BATS is None, reason="Bats is not installed")
@pytest.mark.parametrize("success", [True, False])
def test_actual_bats_protocol_and_exit_status(run_cli: CliRunner, gate_project: Path, success: bool) -> None:
    prepare(
        gate_project,
        {"script.sh": "", "tests/script.bats": '@test "fixture" { ' + ("true" if success else "false") + "; }\n"},
        ("script.sh",),
    )
    assert REAL_BATS is not None
    text = message(run_cli(SCRIPT, env={"RUN_RELATED_TESTS_BATS_BIN": REAL_BATS}), blocked=not success)
    assert ("Bats: 1 passed" if success else "Bats: 0 passed, 1 failed") in text


@pytest.mark.integration
@pytest.mark.skipif(REAL_BATS is None, reason="Bats is not installed")
def test_real_bats_directory_overlap_executes_once_without_recursing(run_cli: CliRunner, gate_project: Path) -> None:
    prepare(
        gate_project,
        {
            ".agents/hooks/rules/related_test_extensions.json": json.dumps(
                {"source.sh": ["tests/domain with spaces/", "./tests/domain with spaces/shared.bats"]}
            ),
            "source.sh": "",
            "tests/domain with spaces/shared.bats": '@test "once" { mkdir "$BATS_SUITE_TMPDIR/once"; }\n',
            "tests/domain with spaces/other.bats": '@test "sibling" { true; }\n',
            "tests/domain with spaces/nested/excluded.bats": '@test "excluded" { false; }\n',
        },
        ("source.sh", "tests/domain with spaces/shared.bats"),
    )
    assert REAL_BATS is not None
    assert "Bats: 2 passed" in message(run_cli(SCRIPT, env={"RUN_RELATED_TESTS_BATS_BIN": REAL_BATS}))


def test_javascript_custom_runner_receives_ci_environment(run_cli: CliRunner, gate_project: Path) -> None:
    prepare(
        gate_project,
        {"package.json": '{"packageManager":"pnpm@10","scripts":{"test":"custom-test-runner"}}', "src/app.ts": ""},
        ("src/app.ts",),
    )
    assert message(run_cli(SCRIPT)).startswith("Verification passed")
    assert calls(gate_project) == [{"tool": "pnpm", "args": ["test"], "ci": "1"}]


def test_pytest_summary_has_no_blank_lines(run_cli: CliRunner, gate_project: Path) -> None:
    prepare(
        gate_project,
        {
            ".agents/hooks/rules/related_test_extensions.json": '{"config/*.toml":["tests/test_first.py","tests/test_second.py"]}',
            "config/app.toml": "",
            "pyproject.toml": "",
            "tests/test_first.py": "",
            "tests/test_second.py": "",
        },
        ("config/app.toml",),
    )
    text = message(run_cli(SCRIPT))
    assert text.startswith("Verification passed · total ")
    assert "pytest: test count unavailable · 2 files · " in text
    assert len(text.splitlines()) == 2
    assert "\n\n" not in text
    assert calls(gate_project)[0]["args"] == [
        "run",
        "--frozen",
        "pytest",
        "--no-header",
        "-q",
        "tests/test_first.py",
        "tests/test_second.py",
    ]


@pytest.mark.parametrize(
    "files,changed,tool,arguments",
    [
        (
            {"Cargo.toml": "", "src/parser.rs": "", "tests/parser.rs": ""},
            "src/parser.rs",
            "cargo",
            ["test", "--test", "parser", "--quiet"],
        ),
        (
            {"pyproject.toml": "", "service.py": "", "tests/service_test.py": ""},
            "service.py",
            "uv",
            ["run", "--frozen", "pytest", "--no-header", "-q", "tests/service_test.py"],
        ),
        (
            {
                "script.sh": "",
                "tests/script.bats": "",
                "tests/extra.bats": "",
                ".agents/hooks/rules/related_test_extensions.json": '{"script.sh":["tests/extra.bats"]}',
            },
            "script.sh",
            "bats",
            ["tests/extra.bats", "tests/script.bats"],
        ),
    ],
)
def test_selected_runner_failure_records_command(
    *, run_cli: CliRunner, gate_project: Path, files: dict, changed: str, tool: str, arguments: list[str]
) -> None:
    prepare(gate_project, files, (changed,))
    text = message(
        run_cli(SCRIPT, env={"TEST_RUNNER_STATUS": "1", "TEST_RUNNER_OUTPUT": "selected test failed"}), blocked=True
    )
    assert "selected test failed" in text
    assert calls(gate_project)[0]["tool"] == tool
    assert calls(gate_project)[0]["args"] == arguments
    directory = Path(
        next(line.removeprefix("Details: ") for line in text.splitlines() if line.startswith("Details: "))
    )
    assert any(f"command: {tool} " in path.read_text() for path in directory.iterdir() if path.is_file())
