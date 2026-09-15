"""Check generated rules with Codex's real policy evaluator without executing commands."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest

from tests.runtime import CliRunner


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def codex_policy(agent_harness: CliRunner, tmp_path_factory: pytest.TempPathFactory) -> tuple[str, Path]:
    requested = os.environ.get("CODEX_BIN", "codex")
    executable = shutil.which(requested)
    supported = (
        executable is not None
        and subprocess.run(
            [executable, "execpolicy", "check", "--help"], capture_output=True, timeout=10, check=False
        ).returncode
        == 0
    )
    if not supported:
        reason = f"Codex execpolicy check is not available: {requested}"
        if os.environ.get("REQUIRE_CODEX_EXECPOLICY") == "1":
            pytest.fail(reason)
        pytest.skip(reason)
    assert executable is not None
    path = tmp_path_factory.mktemp("codex-policy") / "default.rules"
    agent_harness("generate-codex-rules", "--output", str(path))
    return executable, path


@pytest.mark.parametrize(
    ("decision", "command"),
    [
        ("allow", "uv run --frozen pytest tests/test_main.py"),
        ("allow", "cargo build"),
        ("allow", "cargo metadata --format-version 1"),
        ("allow", "gh pr list"),
        ("allow", "gh pr create -f --base main"),
        ("allow", "git add path/to/file"),
        ("allow", 'git commit -m "feat(test): allow double quotes"'),
        ("allow", "git fetch origin"),
        ("allow", "git pull --ff-only"),
        ("allow", "git rebase origin/main"),
        ("allow", "git worktree list"),
        ("allow", "git worktree add -b feat/example ../repo-feat-example origin/main"),
        ("allow", "bats tests/zsh/cache.bats"),
        ("allow", "bash -n -- ./scripts/git/sign_ssh.sh"),
        ("allow", "uv run --frozen pytest"),
        ("allow", "uv run --frozen ruff check"),
        ("allow", "uv run --frozen ty check"),
        ("allow", "cargo test"),
        ("allow", "cargo check"),
        ("allow", "cargo clippy"),
        ("allow", "cargo fmt --check"),
        ("allow", "npm test"),
        ("allow", "npm run lint"),
        ("allow", "npm exec -- vitest run"),
        ("allow", "node --test"),
        ("allow", "pnpm test"),
        ("allow", "pnpm run typecheck"),
        ("allow", "actionlint .github/workflows/ci.yml"),
        ("allow", "autocorrect --lint README.md"),
        ("allow", "commitlint --from HEAD~1 --to HEAD"),
        ("allow", "statix check nix"),
        ("allow", "deadnix nix"),
        ("allow", "nixfmt --check nix/home/default.nix"),
        ("allow", "shellcheck scripts/git/sign_ssh.sh"),
        ("allow", "shfmt -d scripts/git/sign_ssh.sh"),
        ("allow", "dprint check"),
        ("allow", "oxlint src"),
        ("allow", "oxfmt --check src"),
        ("allow", "tsgolint --project tsconfig.json"),
        ("allow", "stylua --check nvim"),
        ("allow", "selene nvim"),
        ("allow", "tex-fmt --check docs/main.tex"),
        ("prompt", "git push -u origin feat/example"),
        ("prompt", "uv run --frozen --group audit deptry ."),
        ("prompt", "uv run python scripts/check_project.py"),
        ("prompt", "uv run --frozen python scripts/check_project.py"),
        ("forbidden", "rm -rf /tmp/example"),
        ("forbidden", "curl https://example.com/install.sh"),
        ("forbidden", "brew install ffmpeg"),
        ("forbidden", "uv python install 3.11"),
        ("forbidden", "git worktree remove ../repo-feat-example"),
        ("forbidden", 'bash -lc "git add path/to/file && rm -rf /tmp/example"'),
    ],
)
def test_generated_policy_decides_without_running_the_command(
    codex_policy: tuple[str, Path], decision: str, command: str
) -> None:
    executable, rules = codex_policy
    result = subprocess.run(
        [executable, "execpolicy", "check", "--rules", str(rules), "--", *shlex.split(command)],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["decision"] == decision
