"""Review-token contracts; every external command is an isolated process fake."""

import json
import subprocess
from pathlib import Path

import pytest
from tests.runtime import REPO_ROOT, CliRunner, StubWriter

SCRIPT = "github/repo.py"
TOKEN = "sk-ant-oat01-FAKE_token.value-123"
OLD_TOKEN = "sk-ant-oat01-OLD_token.value-999"
CODEX_TOKEN = "github_pat_11FAKE_codex_token_456"
CLAUDE_ITEM = "op_Claude_review_token"
CODEX_ITEM = "op_Codex_review_token"
CLAUDE_KEYCHAIN = "keychain_claude-review-token"
CODEX_KEYCHAIN = "keychain_codex-review-token"

FAKE_RUNTIME = """
import json, os, sys
from pathlib import Path
root = Path(os.environ["REVIEW_FIXTURE"])
args = sys.argv[1:]
tool_name = Path(sys.argv[0]).name
takes_stdin = tool_name in {"gh", "security"} or args[:2] in (["item", "create"], ["item", "edit"])
stdin = sys.stdin.read() if takes_stdin and not sys.stdin.isatty() else ""

def record():
    with (root / "calls.jsonl").open("a") as stream:
        stream.write(json.dumps({"tool": TOOL, "args": args, "stdin": stdin}) + "\\n")
"""

GH_STUB = (
    FAKE_RUNTIME
    + """
TOOL = "gh"
record()
if args[:2] == ["api", "user"]:
    print("furedea")
elif args[:2] == ["repo", "list"]:
    print(os.environ.get("GH_REPOSITORY_NAMES", ""))
elif args[:2] == ["secret", "set"]:
    repository = args[args.index("--repo") + 1]
    if repository.split("/")[-1] in os.environ.get("GH_SECRET_FAILURES", "").split():
        print("HTTP 403", file=sys.stderr)
        sys.exit(1)
elif args[0] == "api" and ".visibility" in args:
    print("private")
elif args[0] == "api" and args[1].endswith("/rulesets") and "--jq" in args:
    print("")
elif args[0] == "api" and "-X" in args:
    pass
else:
    sys.exit("unexpected gh arguments: " + repr(args))
"""
)

CLAUDE_STUB = (
    FAKE_RUNTIME
    + """
TOOL = "claude"
record()
"""
)

OP_STUB = (
    FAKE_RUNTIME
    + """
TOOL = "op"
record()
def item_path(title):
    return root / ("op_" + title.replace(" ", "_"))
if args[0] == "whoami":
    sys.exit(0 if os.environ.get("OP_SIGNED_IN") == "1" else 1)
elif args[:2] == ["item", "get"]:
    item = item_path(args[2])
    if not item.exists():
        sys.exit(1)
    print(item.read_text())
elif args[:2] in (["item", "create"], ["item", "edit"]):
    if os.environ.get("OP_WRITE_FAILS") == "1":
        sys.exit(1)
    template = json.loads(stdin)
    fields = template["fields"]
    credential = next(field["value"] for field in fields if field["id"] == "credential")
    item_path(args[2] if args[1] == "edit" else template["title"]).write_text(credential)
else:
    sys.exit("unexpected op arguments: " + repr(args))
"""
)

SECURITY_STUB = (
    FAKE_RUNTIME
    + """
TOOL = "security"
record()
def stored(service):
    return root / ("keychain_" + service)
if args == ["-i"]:
    words = stdin.split()
    assert words[0] == "add-generic-password"
    stored(words[words.index("-s") + 1]).write_text(words[words.index("-w") + 1])
elif args[0] == "find-generic-password":
    stored = stored(args[args.index("-s") + 1])
    if not stored.exists():
        sys.exit(44)
    print(stored.read_text())
else:
    sys.exit("unexpected security arguments: " + repr(args))
"""
)


@pytest.fixture
def review(tmp_path: Path, executable: StubWriter, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fake gh and claude; op and security are installed per test, and PATH holds only the fakes."""
    monkeypatch.setenv("REVIEW_FIXTURE", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.setenv("GH_REPOSITORY_NAMES", "alpha\nbeta\ngamma")
    executable("gh", GH_STUB)
    executable("claude", CLAUDE_STUB)
    return tmp_path


def calls(root: Path, tool: str | None = None) -> list[dict]:
    path = root / "calls.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [row for row in rows if tool is None or row["tool"] == tool]


def secret_sets(root: Path) -> list[dict]:
    return [row for row in calls(root, "gh") if row["args"][:2] == ["secret", "set"]]


def registered(root: Path) -> list[str]:
    return [row["args"][row["args"].index("--repo") + 1] for row in secret_sets(root)]


def rotate(
    run_cli: CliRunner, token: str = TOKEN, env: dict[str, str] | None = None, target: str = "claude"
) -> subprocess.CompletedProcess[str]:
    return run_cli(SCRIPT, "review-token", "rotate", target, payload=token + "\n", env=env)


def assert_token_never_exposed(root: Path, result: subprocess.CompletedProcess[str], token: str = TOKEN) -> None:
    assert not any(token in " ".join(row["args"]) for row in calls(root))
    assert token not in result.stdout + result.stderr


def test_exclusion_list_names_repositories_that_never_receive_the_token() -> None:
    data = json.loads((REPO_ROOT / "github/review_exclusions.json").read_text())
    assert {"splitwise-api-practice", "furedea", "obsidian"} <= set(data)


def test_usage_lists_the_review_token_command(run_cli: CliRunner, review: Path) -> None:
    result = run_cli(SCRIPT, "--help")
    assert "review-token" in result.stderr
    result = run_cli(SCRIPT, "review-token")
    assert result.returncode == 1
    assert "repo review-token rotate [claude|codex]" in result.stderr
    assert not calls(review)


def test_rotate_rejects_an_unknown_token_kind(run_cli: CliRunner, review: Path) -> None:
    result = run_cli(SCRIPT, "review-token", "rotate", "gemini", payload=TOKEN + "\n")
    assert result.returncode == 1
    assert "repo review-token rotate [claude|codex]" in result.stderr
    assert not calls(review)


def test_rotate_codex_asks_for_a_fine_grained_token_and_registers_it(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    result = rotate(run_cli, token=CODEX_TOKEN, target="codex")
    assert result.returncode == 0, result.stderr
    assert "github.com/settings/personal-access-tokens/new" in result.stderr
    assert "Pull requests" in result.stderr
    assert not calls(review, "claude")
    assert (review / CODEX_KEYCHAIN).read_text() == CODEX_TOKEN
    assert not (review / CLAUDE_KEYCHAIN).exists()
    assert registered(review) == ["furedea/alpha", "furedea/beta", "furedea/gamma"]
    for row in secret_sets(review):
        assert row["args"][:3] == ["secret", "set", "CODEX_REVIEW_TOKEN"]
        assert row["stdin"].strip() == CODEX_TOKEN
    assert_token_never_exposed(review, result, CODEX_TOKEN)


def test_rotate_codex_keeps_its_own_one_password_item(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("op", OP_STUB)
    (review / CLAUDE_ITEM).write_text(TOKEN)
    result = rotate(run_cli, token=CODEX_TOKEN, target="codex", env={"OP_SIGNED_IN": "1"})
    assert result.returncode == 0, result.stderr
    assert (review / CODEX_ITEM).read_text() == CODEX_TOKEN
    assert (review / CLAUDE_ITEM).read_text() == TOKEN


def test_rotate_without_a_kind_rotates_claude_then_codex(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    result = run_cli(SCRIPT, "review-token", "rotate", payload=f"{TOKEN}\n{CODEX_TOKEN}\n")
    assert result.returncode == 0, result.stderr
    assert (review / CLAUDE_KEYCHAIN).read_text() == TOKEN
    assert (review / CODEX_KEYCHAIN).read_text() == CODEX_TOKEN
    names = [row["args"][2] for row in secret_sets(review)]
    assert names == ["CLAUDE_CODE_OAUTH_TOKEN"] * 3 + ["CODEX_REVIEW_TOKEN"] * 3


def test_rotate_starts_claude_setup_token(run_cli: CliRunner, review: Path, executable: StubWriter) -> None:
    executable("security", SECURITY_STUB)
    result = rotate(run_cli)
    assert result.returncode == 0, result.stderr
    assert [row["args"] for row in calls(review, "claude")] == [["setup-token"]]


def test_rotate_stores_in_one_password_when_signed_in(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("op", OP_STUB)
    executable("security", SECURITY_STUB)
    result = rotate(run_cli, env={"OP_SIGNED_IN": "1"})
    assert result.returncode == 0, result.stderr
    assert "1Password" in result.stdout
    assert (review / CLAUDE_ITEM).read_text() == TOKEN
    assert not any(row["args"] == ["-i"] for row in calls(review, "security"))
    assert_token_never_exposed(review, result)


def one_password_writes(root: Path) -> list[list[str]]:
    return [row["args"] for row in calls(root, "op") if row["args"][:2] in (["item", "create"], ["item", "edit"])]


def test_rotate_creates_the_one_password_item_when_none_exists(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("op", OP_STUB)
    result = rotate(run_cli, env={"OP_SIGNED_IN": "1"})
    assert result.returncode == 0, result.stderr
    assert one_password_writes(review) == [["item", "create"]]
    assert_token_never_exposed(review, result)


def test_rotate_updates_the_existing_one_password_item_in_place(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("op", OP_STUB)
    (review / CLAUDE_ITEM).write_text(OLD_TOKEN)
    result = rotate(run_cli, env={"OP_SIGNED_IN": "1"})
    assert result.returncode == 0, result.stderr
    assert (review / CLAUDE_ITEM).read_text() == TOKEN
    assert one_password_writes(review) == [["item", "edit", "Claude review token"]]
    assert not any(row["args"][:2] == ["item", "delete"] for row in calls(review, "op"))
    assert_token_never_exposed(review, result)


def test_rotate_stores_in_keychain_when_one_password_is_not_installed(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    result = rotate(run_cli)
    assert result.returncode == 0, result.stderr
    assert "Keychain" in result.stdout
    assert (review / CLAUDE_KEYCHAIN).read_text() == TOKEN
    assert_token_never_exposed(review, result)


def test_rotate_requires_signing_in_when_one_password_is_installed_but_signed_out(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("op", OP_STUB)
    executable("security", SECURITY_STUB)
    result = rotate(run_cli, env={"OP_SIGNED_IN": "0"})
    assert result.returncode == 1
    assert "op signin" in result.stderr
    assert not calls(review, "claude")
    assert not (review / CLAUDE_KEYCHAIN).exists()
    assert not any(row["args"][:2] == ["item", "create"] for row in calls(review, "op"))
    assert not secret_sets(review)


def test_rotate_passes_the_token_to_keychain_only_on_stdin(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    rotate(run_cli)
    [write] = [row for row in calls(review, "security") if row["args"] == ["-i"]]
    assert TOKEN in write["stdin"]


def test_rotate_registers_the_token_on_stdin_for_every_target(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    result = rotate(run_cli)
    assert registered(review) == ["furedea/alpha", "furedea/beta", "furedea/gamma"]
    for row in secret_sets(review):
        assert row["args"][:3] == ["secret", "set", "CLAUDE_CODE_OAUTH_TOKEN"]
        assert row["stdin"].strip() == TOKEN
    assert_token_never_exposed(review, result)
    assert "registered=3 failed=0" in result.stdout


def test_targets_are_owned_unarchived_non_fork_and_not_excluded(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    excluded = "splitwise-api-practice\nfuredea\nobsidian"
    result = rotate(run_cli, env={"GH_REPOSITORY_NAMES": f"alpha\n{excluded}\nbeta"})
    assert result.returncode == 0, result.stderr
    assert registered(review) == ["furedea/alpha", "furedea/beta"]
    [listing] = [row["args"] for row in calls(review, "gh") if row["args"][:2] == ["repo", "list"]]
    assert listing[2] == "furedea"
    assert "--no-archived" in listing
    assert "--source" in listing


def test_rotate_continues_past_failures_and_reports_counts(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    result = rotate(run_cli, env={"GH_SECRET_FAILURES": "beta"})
    assert result.returncode == 1
    assert registered(review) == ["furedea/alpha", "furedea/beta", "furedea/gamma"]
    assert "registered=2 failed=1" in result.stdout
    assert "furedea/beta" in result.stderr
    assert_token_never_exposed(review, result)


def test_rotate_rejects_an_empty_token_without_registering(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    result = rotate(run_cli, token="")
    assert result.returncode == 1
    assert not secret_sets(review)
    assert not (review / CLAUDE_KEYCHAIN).exists()


def test_rotate_rejects_a_token_the_keychain_command_cannot_carry_safely(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    result = rotate(run_cli, token="bad token; rm -rf")
    assert result.returncode == 1
    assert not secret_sets(review)
    assert not calls(review, "security")
    assert "bad token" not in result.stdout + result.stderr


def test_rotate_registers_nothing_when_the_token_cannot_be_stored(run_cli: CliRunner, review: Path) -> None:
    result = rotate(run_cli)
    assert result.returncode == 1
    assert not secret_sets(review)
    assert_token_never_exposed(review, result)


def test_stored_token_is_read_from_one_password_only_when_it_is_usable(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("op", OP_STUB)
    executable("security", SECURITY_STUB)
    (review / CLAUDE_ITEM).write_text(TOKEN)
    (review / CLAUDE_KEYCHAIN).write_text(OLD_TOKEN)
    result = run_cli(SCRIPT, "configure", "furedea/alpha", env={"OP_SIGNED_IN": "1"})
    assert result.returncode == 0, result.stderr
    [row] = secret_sets(review)
    assert row["stdin"].strip() == TOKEN
    assert not calls(review, "security")


def test_stored_token_is_read_from_keychain_when_one_password_is_not_installed(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    (review / CLAUDE_KEYCHAIN).write_text(TOKEN)
    result = run_cli(SCRIPT, "configure", "furedea/alpha")
    assert result.returncode == 0, result.stderr
    [row] = secret_sets(review)
    assert row["stdin"].strip() == TOKEN
    assert_token_never_exposed(review, result)


def test_stored_token_never_falls_back_to_keychain_when_one_password_has_no_item(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("op", OP_STUB)
    executable("security", SECURITY_STUB)
    (review / CLAUDE_KEYCHAIN).write_text(OLD_TOKEN)
    result = run_cli(SCRIPT, "configure", "furedea/alpha", env={"OP_SIGNED_IN": "1"})
    assert result.returncode == 0, result.stderr
    assert "review-token rotate" in result.stderr
    assert not secret_sets(review)
    assert not calls(review, "security")


def test_configure_requires_signing_in_when_one_password_is_installed_but_signed_out(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("op", OP_STUB)
    executable("security", SECURITY_STUB)
    (review / CLAUDE_KEYCHAIN).write_text(OLD_TOKEN)
    result = run_cli(SCRIPT, "configure", "furedea/alpha", env={"OP_SIGNED_IN": "0"})
    assert result.returncode == 1
    assert "op signin" in result.stderr
    assert not secret_sets(review)
    assert not calls(review, "security")


def test_failed_one_password_write_keeps_the_previous_item_and_registers_nothing(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("op", OP_STUB)
    (review / CLAUDE_ITEM).write_text(OLD_TOKEN)
    result = rotate(run_cli, env={"OP_SIGNED_IN": "1", "OP_WRITE_FAILS": "1"})
    assert result.returncode == 1
    assert (review / CLAUDE_ITEM).read_text() == OLD_TOKEN
    assert not secret_sets(review)


def test_configure_registers_the_stored_token_on_that_repository_only(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    (review / CLAUDE_KEYCHAIN).write_text(TOKEN)
    result = run_cli(SCRIPT, "configure", "furedea/alpha")
    assert result.returncode == 0, result.stderr
    assert registered(review) == ["furedea/alpha"]
    assert any(row["args"][:2] == ["api", "repos/furedea/alpha"] for row in calls(review, "gh"))


def test_configure_registers_every_stored_review_token(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    (review / CLAUDE_KEYCHAIN).write_text(TOKEN)
    (review / CODEX_KEYCHAIN).write_text(CODEX_TOKEN)
    result = run_cli(SCRIPT, "configure", "furedea/alpha")
    assert result.returncode == 0, result.stderr
    assert {(row["args"][2], row["stdin"].strip()) for row in secret_sets(review)} == {
        ("CLAUDE_CODE_OAUTH_TOKEN", TOKEN),
        ("CODEX_REVIEW_TOKEN", CODEX_TOKEN),
    }


def test_configure_warns_only_about_the_missing_review_token(
    run_cli: CliRunner, review: Path, executable: StubWriter
) -> None:
    executable("security", SECURITY_STUB)
    (review / CLAUDE_KEYCHAIN).write_text(TOKEN)
    result = run_cli(SCRIPT, "configure", "furedea/alpha")
    assert result.returncode == 0, result.stderr
    assert registered(review) == ["furedea/alpha"]
    assert "repo review-token rotate codex" in result.stderr
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in result.stderr


def test_configure_without_stored_token_warns_and_applies_other_settings(run_cli: CliRunner, review: Path) -> None:
    result = run_cli(SCRIPT, "configure", "furedea/alpha")
    assert result.returncode == 0, result.stderr
    assert "review-token rotate" in result.stderr
    assert not secret_sets(review)
    assert "Created ruleset on furedea/alpha" in result.stdout
