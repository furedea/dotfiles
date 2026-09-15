"""Secret-content decisions using public synthetic samples and real CLI processes."""

import json
from pathlib import Path
import shutil

import pytest

from conftest import REPO_ROOT, CliRunner


SCRIPT = "agents/hooks/guard_file.py"


@pytest.fixture
def sensitive_samples() -> dict[str, str]:
    return json.loads(Path(__file__).with_name("secret_content_samples.json").read_text())


@pytest.fixture(autouse=True)
def scanner_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "patterns.json"
    shutil.copyfile(REPO_ROOT / "agents/hooks/rules/secret_content_patterns.json", path)
    monkeypatch.setenv("AGENT_SECRET_CONTENT_PATTERNS", str(path))
    return path


@pytest.mark.parametrize(
    "sample",
    ["aws_key", "github_token", "rsa_header", "openai_key", "bearer_token", "postgres_url", "api_assignment"],
)
def test_prompt_blocks_sensitive_content(run_cli: CliRunner, sensitive_samples: dict[str, str], sample: str) -> None:
    text = sensitive_samples[sample]
    if sample == "aws_key":
        text = "my key is " + text
    result = run_cli(SCRIPT, "prompt", payload={"prompt": text})
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout)["decision"] == "block"


@pytest.mark.parametrize("text", ["please fix the bug in main.py", ""], ids=["safe-text", "empty-prompt"])
def test_prompt_allows_safe_content(run_cli: CliRunner, text: str) -> None:
    result = run_cli(SCRIPT, "prompt", payload={"prompt": text})
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("sample", ["aws_key", "mysql_url"])
def test_read_denies_sensitive_file_content(
    run_cli: CliRunner, tmp_path: Path, sensitive_samples: dict[str, str], sample: str
) -> None:
    text = sensitive_samples[sample]
    if sample == "aws_key":
        text = "config = " + text
    path = tmp_path / "input.txt"
    path.write_text(text + "\n")
    result = run_cli(SCRIPT, "read", payload={"tool_input": {"file_path": str(path)}})
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("exists", [True, False], ids=["clean-file", "missing-file"])
def test_read_allows_clean_or_missing_files(run_cli: CliRunner, tmp_path: Path, exists: bool) -> None:
    path = tmp_path / "input.txt"
    if exists:
        path.write_text("hello world\n")
    result = run_cli(SCRIPT, "read", payload={"tool_input": {"file_path": str(path)}})
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


@pytest.mark.parametrize(
    "field,sample",
    [("content", "private_header"), ("content", "anthropic_assignment"), ("new_string", "edit_assignment")],
)
def test_write_denies_sensitive_content_or_replacement(
    run_cli: CliRunner, sensitive_samples: dict[str, str], field: str, sample: str
) -> None:
    values = {"content": "", "new_string": "", field: sensitive_samples[sample]}
    result = run_cli(SCRIPT, "write", payload={"tool_input": values})
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("text", ["def hello(): pass", ""], ids=["safe-content", "empty-write"])
def test_write_allows_safe_content(run_cli: CliRunner, text: str) -> None:
    result = run_cli(SCRIPT, "write", payload={"tool_input": {"content": text, "new_string": ""}})
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("arguments", [(), ("--help",)], ids=["missing-mode", "help"])
def test_missing_mode_or_help_reports_usage(run_cli: CliRunner, arguments: tuple[str, ...]) -> None:
    result = run_cli(SCRIPT, *arguments)
    assert result.returncode == 1
    assert "Usage" in result.stderr


def test_missing_optional_patterns_skip_scanning(
    run_cli: CliRunner, scanner_policy: Path, sensitive_samples: dict[str, str]
) -> None:
    scanner_policy.unlink()
    result = run_cli(SCRIPT, "prompt", payload={"prompt": sensitive_samples["aws_key"]})
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""
