"""Allowed-command contracts inspect text without executing the submitted commands."""

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
pytestmark = pytest.mark.usefixtures("isolated_project")


@pytest.mark.parametrize(
    "command,status,fragments",
    [
        pytest.param("echo hello", 0, [], id="passes through non-governed commands unchanged"),
        pytest.param("git status", 0, [], id="passes through git commands that are not governed"),
        pytest.param("gh pr list", 0, [], id="governed command matching allowlist is permitted"),
        pytest.param("env gh pr merge 42", 2, ["gh pr merge 42"], id="blocks env wrapper around a governed command"),
        pytest.param("command gh pr merge 42", 2, [], id="blocks command builtin around a governed command"),
        pytest.param("/opt/homebrew/bin/gh pr merge 42", 2, [], id="blocks governed commands invoked by path"),
        pytest.param("/opt/homebrew/bin/gh pr list", 0, [], id="allows precise forms invoked by path"),
        pytest.param(
            "git -c core.fsmonitor=false rebase -i origin/main", 2, [], id="governs git behind global options"
        ),
        pytest.param(
            "git -c core.fsmonitor=false branch --show-current",
            0,
            [],
            id="allows precise forms behind git global options",
        ),
        pytest.param(
            "env BATS_TMPDIR=/tmp bats tests/zsh/cache.bats",
            0,
            [],
            id="allows env wrapper around an allowed verification command",
        ),
        pytest.param("env CI=1 cargo test > /tmp/blocked", 2, [], id="blocks redirections behind wrappers"),
        pytest.param("/usr/bin/time -p ls_lint", 0, [], id="passes through wrapped non-governed commands"),
        pytest.param("command -v rg", 0, [], id="passes through command lookups"),
        pytest.param("uv run --frozen ruff check", 0, [], id="allows Python verification commands 1"),
        pytest.param("uv run --frozen ruff format --check", 0, [], id="allows Python verification commands 2"),
        pytest.param("uv run --frozen ty check", 0, [], id="allows Python verification commands 3"),
        pytest.param("uv run --frozen ty check src tests", 0, [], id="allows Python verification commands 4"),
        pytest.param("uv run --frozen pytest", 0, [], id="allows Python verification commands 5"),
        pytest.param(
            "uv run --frozen pytest tests/test_main.py -k test_main --cov",
            0,
            [],
            id="allows Python verification commands 6",
        ),
        pytest.param("uv run --frozen pytest tests/test_main.py", 0, [], id="allows Python verification commands 7"),
        pytest.param(
            "uv run --frozen --with pytest pytest tests/test_main.py -k test_main",
            0,
            [],
            id="allows Python verification commands 8",
        ),
        pytest.param(
            "uv run --frozen --group audit deptry .",
            0,
            [],
            id="leaves broad audit execution for provider approval and allows named package checks 1",
        ),
        pytest.param(
            "uv run --frozen --group audit vulture",
            0,
            [],
            id="leaves broad audit execution for provider approval and allows named package checks 2",
        ),
        pytest.param(
            "pnpm run knip",
            0,
            [],
            id="leaves broad audit execution for provider approval and allows named package checks 3",
        ),
        pytest.param(
            "pnpm run knip:production",
            0,
            [],
            id="leaves broad audit execution for provider approval and allows named package checks 4",
        ),
        pytest.param(
            "git commit -m 'feat(test): allow single quoted messages'",
            0,
            [],
            id="allows git commit messages with single or double quotes 1",
        ),
        pytest.param(
            'git commit -m "feat(test): allow double quoted messages"',
            0,
            [],
            id="allows git commit messages with single or double quotes 2",
        ),
        pytest.param(
            "git commit -m 'feat(test): subject' -m 'Body paragraph.' -m 'Co-Authored-By: Example <e@example.com>'",
            0,
            [],
            id="allows git commit bodies and trailers as repeated single quoted messages",
        ),
        pytest.param("uv run --frozen ruff check", 0, [], id="allows Python style frozen ruff commands 1"),
        pytest.param("uv run --frozen ruff check src/main.py", 0, [], id="allows Python style frozen ruff commands 2"),
        pytest.param("uv run --frozen ruff format --check", 0, [], id="allows Python style frozen ruff commands 3"),
        pytest.param(
            "uv run --frozen ruff format tests/test_main.py", 0, [], id="allows Python style frozen ruff commands 4"
        ),
        pytest.param(
            'uv run --frozen pytest tests/test_main.py -k "test_main or test_error"',
            0,
            [],
            id="allows quoted test selection and colon-named package checks 1",
        ),
        pytest.param(
            "npm run format:check", 0, [], id="allows quoted test selection and colon-named package checks 2"
        ),
        pytest.param(
            "pnpm run format:check", 0, [], id="allows quoted test selection and colon-named package checks 3"
        ),
        pytest.param(
            "uv run --frozen ty server", 2, [], id="blocks unrelated subcommands within verification tool prefixes 1"
        ),
        pytest.param(
            "uv run --frozen ruff clean", 2, [], id="blocks unrelated subcommands within verification tool prefixes 2"
        ),
        pytest.param(
            "bats tests/zsh/cache.bats",
            0,
            [],
            id="allows local verification commands 1",
        ),
        pytest.param("actionlint .github/workflows/ci.yml", 0, [], id="allows local verification commands 2"),
        pytest.param(
            "shellcheck agents/hooks/guard_allowed_commands.sh", 0, [], id="allows local verification commands 3"
        ),
        pytest.param(
            "shfmt -w agents/hooks/guard_allowed_commands.sh", 0, [], id="allows local verification commands 4"
        ),
        pytest.param("dprint check", 0, [], id="allows local verification commands 5"),
        pytest.param("dprint fmt README.md", 0, [], id="allows local verification commands 6"),
        pytest.param("nixfmt nix/home/default.nix", 0, [], id="allows local verification commands 7"),
        pytest.param("statix check nix", 0, [], id="allows local verification commands 8"),
        pytest.param("deadnix nix", 0, [], id="allows local verification commands 9"),
        pytest.param("cargo test", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 1"),
        pytest.param(
            "cargo clippy --all-targets --all-features",
            0,
            [],
            id="allows Rust TypeScript Lua and LaTeX quality commands 2",
        ),
        pytest.param("cargo fmt --check", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 3"),
        pytest.param("pnpm test -- --run", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 4"),
        pytest.param("pnpm exec oxlint src", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 5"),
        pytest.param("npm run lint", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 6"),
        pytest.param("oxfmt --check src", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 7"),
        pytest.param("oxlint src", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 8"),
        pytest.param(
            "tsgolint --project tsconfig.json", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 9"
        ),
        pytest.param("stylua --check nvim", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 10"),
        pytest.param("selene nvim", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 11"),
        pytest.param(
            "tex-fmt --check docs/main.tex", 0, [], id="allows Rust TypeScript Lua and LaTeX quality commands 12"
        ),
        pytest.param(
            "cargo test > /tmp/blocked",
            2,
            [],
            id="blocks shell metacharacters in automatically allowed verification commands 1",
        ),
        pytest.param(
            "pnpm test $(touch /tmp/blocked)",
            2,
            [],
            id="blocks shell metacharacters in automatically allowed verification commands 2",
        ),
        pytest.param(
            "dprint fmt README.md $(touch /tmp/blocked)",
            2,
            [],
            id="blocks shell metacharacters in automatically allowed formatting commands",
        ),
        pytest.param(
            "uv run --frozen pytest $(touch /tmp/blocked)",
            2,
            [],
            id="blocks shell metacharacters in automatically allowed Python verification 1",
        ),
        pytest.param(
            "uv run --frozen pytest `touch /tmp/blocked`",
            2,
            [],
            id="blocks shell metacharacters in automatically allowed Python verification 2",
        ),
        pytest.param(
            "uv run --frozen pytest > /tmp/blocked",
            2,
            [],
            id="blocks shell metacharacters in automatically allowed Python verification 3",
        ),
        pytest.param('uv run python -c "print(1)"', 0, [], id="leaves Python execution to provider approval 1"),
        pytest.param(
            "uv run python scripts/check_project.py", 0, [], id="leaves Python execution to provider approval 2"
        ),
        pytest.param(
            "uv run --frozen python scripts/check_project.py",
            0,
            [],
            id="leaves Python execution to provider approval 3",
        ),
        pytest.param(
            "uv run --group audit deptry .", 0, [], id="leaves other execution commands to their existing policies"
        ),
        pytest.param(
            "bash -n -- ./scripts/git/sign_ssh.sh",
            0,
            [],
            id="allows syntax checks of one explicit relative file 1",
        ),
        pytest.param(
            'bash -n -- "./path with spaces/script.sh"',
            0,
            [],
            id="allows syntax checks of one explicit relative file 2",
        ),
        pytest.param(
            'git commit -m "feat(test): $(touch /tmp/blocked)"',
            2,
            [],
            id="blocks command substitution in double quoted git commit messages 1",
        ),
        pytest.param(
            'git commit -m "feat(test): `touch /tmp/blocked`"',
            2,
            [],
            id="blocks command substitution in double quoted git commit messages 2",
        ),
        pytest.param("git commit -F .git/COMMIT_MSG", 2, [], id="blocks git commit messages read from files 1"),
        pytest.param("git commit --amend -F message.txt", 2, [], id="blocks git commit messages read from files 2"),
        pytest.param("git add bot/main.py", 0, [], id="allows git add explicit paths 1"),
        pytest.param("git add bot/main.py tests/bot/test_main.py", 0, [], id="allows git add explicit paths 2"),
        pytest.param("git add -- path/to/file", 0, [], id="allows git add explicit paths 3"),
        pytest.param('git ls-files "*.nix"', 0, [], id="allows git ls-files extension globs 1"),
        pytest.param('git ls-files "*.ts"', 0, [], id="allows git ls-files extension globs 2"),
        pytest.param("git ls-files", 2, [], id="blocks broad git ls-files forms 1"),
        pytest.param('git ls-files "."', 2, [], id="blocks broad git ls-files forms 2"),
        pytest.param('git ls-files "*.nix" --others', 2, [], id="blocks broad git ls-files forms 3"),
        pytest.param("git branch --show-current", 0, [], id="allows safe git branch helper operations 1"),
        pytest.param("git branch --list feat/topic", 0, [], id="allows safe git branch helper operations 2"),
        pytest.param("git branch -m feat/topic", 0, [], id="allows safe git branch helper operations 3"),
        pytest.param("git worktree list", 0, [], id="allows worktree branch creation commands 1"),
        pytest.param(
            "git worktree add -b feat/worktree-branch-delivery ../agent-harness-feat-worktree-branch-delivery origin/main",
            0,
            [],
            id="allows worktree branch creation commands 2",
        ),
        pytest.param(
            "git worktree remove ../agent-harness-feat-worktree-branch-delivery",
            2,
            [],
            id="blocks worktree maintenance commands 1",
        ),
        pytest.param("git worktree prune", 2, [], id="blocks worktree maintenance commands 2"),
        pytest.param("git worktree move ../old ../new", 2, [], id="blocks worktree maintenance commands 3"),
        pytest.param("git worktree repair", 2, [], id="blocks worktree maintenance commands 4"),
        pytest.param("git fetch origin", 0, [], id="allows PR delivery commands 1"),
        pytest.param("git pull --ff-only", 0, [], id="allows PR delivery commands 2"),
        pytest.param("git push -u origin feat/agent-pr-delivery", 0, [], id="allows PR delivery commands 3"),
        pytest.param(
            "git push --set-upstream origin fix/parser-empty-input", 0, [], id="allows PR delivery commands 4"
        ),
        pytest.param("gh pr create -f --base main", 0, [], id="allows PR delivery commands 5"),
        pytest.param("git rebase origin/main", 0, [], id="allows narrow pre-PR rebase commands 1"),
        pytest.param("git rebase origin/release/1.2", 0, [], id="allows narrow pre-PR rebase commands 2"),
        pytest.param("git rebase --continue", 0, [], id="allows narrow pre-PR rebase commands 3"),
        pytest.param("git rebase --abort", 0, [], id="allows narrow pre-PR rebase commands 4"),
        pytest.param("git rebase -i origin/main", 2, [], id="blocks broad rebase commands 1"),
        pytest.param("git rebase --onto origin/main HEAD~2", 2, [], id="blocks broad rebase commands 2"),
        pytest.param("git rebase main", 2, [], id="blocks broad rebase commands 3"),
        pytest.param('git commit -m "hello world"', 0, [], id="allows normal git commit forms 1"),
        pytest.param("git commit --amend -m fix", 0, [], id="allows normal git commit forms 2"),
        pytest.param("git commit --amend --no-edit", 0, [], id="allows normal git commit forms 3"),
        pytest.param(
            "gh api repos/owner/repo/unknown-endpoint",
            2,
            ["BLOCKED"],
            id="governed command not in allowlist is blocked",
        ),
        pytest.param(
            "gh pr merge 42", 2, ["gh pr merge 42"], id="blocked output includes the offending command segment"
        ),
        pytest.param("gh pr list | head -5", 0, [], id="splits on pipe: governed | non-governed"),
        pytest.param("echo test | gh pr list", 0, [], id="splits on pipe: non-governed | governed"),
        pytest.param("gh pr list | gh pr merge 42", 2, [], id="splits on pipe: blocked segment in pipeline"),
        pytest.param("gh pr list && echo done", 0, [], id="splits on &&: governed && non-governed"),
        pytest.param("gh pr list && gh pr merge 42", 2, [], id="splits on &&: blocked segment after &&"),
        pytest.param("gh pr merge 42 && gh pr list", 2, [], id="splits on &&: blocked segment before &&"),
        pytest.param("gh pr list || echo failed", 0, [], id="splits on ||: governed || non-governed"),
        pytest.param("gh pr list || gh pr merge 42", 2, [], id="splits on ||: blocked segment after ||"),
        pytest.param("gh pr list; echo done", 0, [], id="splits on semicolon: governed; non-governed"),
        pytest.param("gh pr list; gh pr merge 42", 2, [], id="splits on semicolon: blocked segment after ;"),
        pytest.param("gh pr list & echo done", 0, [], id="splits on background &"),
        pytest.param("gh pr list & gh pr merge 42", 2, [], id="splits on background &: blocked segment"),
        pytest.param("gh pr list 2>&1", 0, [], id="does NOT split on & inside 2>&1 redirection"),
        pytest.param("gh pr list >&2", 0, [], id="does NOT split on & inside >&2 redirection"),
        pytest.param("gh pr list 2>/dev/null", 0, [], id="does NOT split on & inside 2>/dev/null"),
        pytest.param("gh pr list 2>&1 & echo done", 0, [], id="background & after redirection is still split"),
        pytest.param("  gh pr list", 0, [], id="trims leading whitespace from segments"),
        pytest.param("gh pr list  ", 0, [], id="trims trailing whitespace from segments"),
        pytest.param("  gh pr list  ", 0, [], id="trims whitespace from both ends"),
        pytest.param(
            "  git branch --show-current  ", 0, [], id="trims both ends of commands matched by anchored rules"
        ),
        pytest.param(
            "git status && git branch --show-current && git worktree list",
            0,
            [],
            id="allows anchored commands between compound separators",
        ),
        pytest.param("  gh pr list  |  head -5  ", 0, [], id="trims whitespace in piped segments"),
        pytest.param("gh pr list 2>&1", 0, [], id="strips trailing 2>&1 before matching"),
        pytest.param("gh pr list >&2", 0, [], id="strips trailing >&2 before matching"),
        pytest.param("gh pr list 2>/dev/null", 0, [], id="strips trailing 2>/dev/null before matching"),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments --jq '.[].body | length'",
            0,
            [],
            id="does not split on pipe inside single quotes",
        ),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments --jq '.[] ; .body'",
            0,
            [],
            id="does not split on semicolon inside single quotes",
        ),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments --jq '.[] && .body'",
            0,
            [],
            id="does not split on && inside single quotes",
        ),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments --jq '.[] || .body'",
            0,
            [],
            id="does not split on || inside single quotes",
        ),
        pytest.param("gh pr list && gh pr status", 0, [], id="allows when all governed segments match allowlist"),
        pytest.param(
            "gh pr list && gh pr merge 42 && gh pr status", 2, [], id="blocks when any governed segment is not allowed"
        ),
        pytest.param("", 0, [], id="empty command"),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments/99/replies -f body='it'\\''s great'",
            0,
            [],
            id="apostrophe in a single-quoted body",
        ),
        pytest.param("bash -n", 2, [], id="syntax check arguments bash -n"),
        pytest.param("bash -n ./script.sh", 2, [], id="syntax check arguments bash -n ./script.sh"),
        pytest.param("bash -n +n -- ./script.sh", 2, [], id="syntax check arguments bash -n +n -- ./script.sh"),
        pytest.param("bash -n -i -- ./script.sh", 2, [], id="syntax check arguments bash -n -i -- ./script.sh"),
        pytest.param("bash -n -c 'echo example'", 2, [], id="syntax check arguments bash -n -c 'echo example'"),
        pytest.param(
            "bash -n -- ./first.sh ./second.sh", 2, [], id="syntax check arguments bash -n -- ./first.sh ./second.sh"
        ),
        pytest.param("bash -n -- ./script.sh +n", 2, [], id="syntax check arguments bash -n -- ./script.sh +n"),
        pytest.param(
            "bash -n -- ./script.sh > /tmp/output",
            2,
            [],
            id="syntax check arguments bash -n -- ./script.sh > /tmp/output",
        ),
    ],
)
def test_allowed_command_contract(
    capsys: pytest.CaptureFixture[str], command: str, status: int, fragments: list[str]
) -> None:
    assert guard.check("allowed", {"tool_input": {"command": command}}) == status
    captured = capsys.readouterr()
    assert captured.out == ""
    for fragment in fragments:
        assert fragment in captured.err
