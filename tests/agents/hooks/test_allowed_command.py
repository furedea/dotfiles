"""Allowed-command contracts inspect text without executing the submitted commands."""

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
pytestmark = pytest.mark.usefixtures("isolated_project")


@pytest.mark.parametrize(
    "command,decision,fragments",
    [
        pytest.param("echo hello", "allow", [], id="passes through non-governed commands unchanged"),
        pytest.param("git status", "allow", [], id="passes through git commands that are not governed"),
        pytest.param("gh pr list", "allow", [], id="governed command matching allowlist is permitted"),
        pytest.param(
            "env gh pr review 42 --approve",
            "ask",
            ["gh pr review 42 --approve"],
            id="blocks env wrapper around a governed command",
        ),
        pytest.param(
            "command gh pr review 42 --approve", "ask", [], id="blocks command builtin around a governed command"
        ),
        pytest.param(
            "/opt/homebrew/bin/gh pr review 42 --approve", "ask", [], id="blocks governed commands invoked by path"
        ),
        pytest.param("/opt/homebrew/bin/gh pr list", "allow", [], id="allows precise forms invoked by path"),
        pytest.param(
            "git -c core.fsmonitor=false rebase -i origin/main", "ask", [], id="governs git behind global options"
        ),
        pytest.param(
            "git -c core.fsmonitor=false branch --show-current",
            "allow",
            [],
            id="allows precise forms behind git global options",
        ),
        pytest.param(
            "env BATS_TMPDIR=/tmp bats tests/zsh/cache.bats",
            "allow",
            [],
            id="allows env wrapper around an allowed verification command",
        ),
        pytest.param("env CI=1 cargo test > /tmp/blocked", "ask", [], id="blocks redirections behind wrappers"),
        pytest.param("/usr/bin/time -p ls_lint", "allow", [], id="passes through wrapped non-governed commands"),
        pytest.param("command -v rg", "allow", [], id="passes through command lookups"),
        pytest.param("git switch -c feat/example", "allow", [], id="allows reversible git operations 1"),
        pytest.param("git restore --staged foo.py", "allow", [], id="allows reversible git operations 2"),
        pytest.param("git stash push -m 'wip'", "allow", [], id="allows reversible git operations 3"),
        pytest.param("git reset --soft HEAD~1", "allow", [], id="allows reversible git operations 4"),
        pytest.param("git merge origin/main", "allow", [], id="allows reversible git operations 5"),
        pytest.param("git cherry-pick abc1234", "allow", [], id="allows reversible git operations 6"),
        pytest.param("git revert abc1234", "allow", [], id="allows reversible git operations 7"),
        pytest.param("git tag v1.2.3", "allow", [], id="allows reversible git operations 8"),
        pytest.param("git rm --cached foo.py", "allow", [], id="allows reversible git operations 9"),
        pytest.param("git mv a.py b.py", "allow", [], id="allows reversible git operations 10"),
        pytest.param(
            "git push --force-with-lease --force-if-includes origin feat/example",
            "allow",
            [],
            id="allows leased force pushes",
        ),
        pytest.param("git switch -f main", "ask", [], id="blocks destructive git forms in the allowlist 1"),
        pytest.param("git restore foo.py", "ask", [], id="blocks destructive git forms in the allowlist 2"),
        pytest.param("git reset --hard HEAD", "ask", [], id="blocks destructive git forms in the allowlist 3"),
        pytest.param("git tag -d v1.2.3", "ask", [], id="blocks destructive git forms in the allowlist 4"),
        pytest.param("git rm -f foo.py", "ask", [], id="blocks destructive git forms in the allowlist 5"),
        pytest.param(
            "git push --force-with-lease origin feat/example",
            "ask",
            [],
            id="blocks destructive git forms in the allowlist 6",
        ),
        pytest.param("git status --porcelain=v1 --branch", "allow", [], id="allows read-only git inspection 1"),
        pytest.param("git log --oneline -5 --format='%h %s'", "allow", [], id="allows read-only git inspection 2"),
        pytest.param("git config --get user.name", "allow", [], id="allows read-only git inspection 3"),
        pytest.param("git remote -v", "allow", [], id="allows read-only git inspection 4"),
        pytest.param("git config user.name example", "ask", [], id="blocks git configuration writes"),
        pytest.param("gh pr review 42 --comment -b 'Looks good'", "allow", [], id="allows reviewable gh operations 1"),
        pytest.param("gh pr close 42", "allow", [], id="allows reviewable gh operations 2"),
        pytest.param("gh run rerun 123", "allow", [], id="allows reviewable gh operations 3"),
        pytest.param("gh api user", "allow", [], id="allows reviewable gh operations 4"),
        pytest.param("gh repo view owner/repo", "allow", [], id="allows reviewable gh operations 5"),
        pytest.param(
            "gh api repos/owner/repo/issues/1 --method DELETE",
            "ask",
            [],
            id="blocks gh api writes outside enumerated forms",
        ),
        pytest.param("gh stack view --short", "allow", [], id="allows stacked pull request commands 1"),
        pytest.param(
            "gh stack init test/repro-tax-rounding", "allow", [], id="allows stacked pull request commands 2"
        ),
        pytest.param("gh stack add fix/tax-rounding", "allow", [], id="allows stacked pull request commands 3"),
        pytest.param("gh stack submit --auto", "allow", [], id="allows stacked pull request commands 4"),
        pytest.param("gh stack init", "ask", ["gh stack init"], id="blocks interactive stack commands 1"),
        pytest.param("gh stack submit", "ask", ["gh stack submit"], id="blocks interactive stack commands 2"),
        pytest.param(
            "uv run --frozen bats tests/zsh/cache.bats", "allow", [], id="allows verification and build commands 1"
        ),
        pytest.param("nix flake check", "allow", [], id="allows verification and build commands 2"),
        pytest.param(
            "nix eval --json .#packages --apply 'ps: map (p: p.name) ps'",
            "allow",
            [],
            id="allows verification and build commands 3",
        ),
        pytest.param("home-manager build --flake .#kaito", "allow", [], id="allows verification and build commands 4"),
        pytest.param("cargo fmt", "allow", [], id="allows verification and build commands 5"),
        pytest.param(
            "python3 -I -B github/repo.py --help", "allow", [], id="allows verification and build commands 6"
        ),
        pytest.param("lefthook run pre-commit", "allow", [], id="allows verification and build commands 7"),
        pytest.param("pnpm install --frozen-lockfile", "allow", [], id="allows verification and build commands 8"),
        pytest.param("npm ci", "allow", [], id="allows verification and build commands 9"),
        pytest.param("rg -n 'foo$|bar' agents", "allow", [], id="allows read-only inspection with quoted patterns 1"),
        pytest.param(
            "jq -r '.rules[] | .prefix' agents/command_permissions.json",
            "allow",
            [],
            id="allows read-only inspection with quoted patterns 2",
        ),
        pytest.param("sed -n '1,40p' README.md", "allow", [], id="allows read-only inspection with quoted patterns 3"),
        pytest.param("find . -name '*.py'", "allow", [], id="allows read-only inspection with quoted patterns 4"),
        pytest.param("cat README.md > copy.md", "ask", [], id="blocks redirections from read-only commands"),
        pytest.param("sed -i 's/a/b/' README.md", "allow", [], id="leaves asked commands to provider approval 1"),
        pytest.param("python3 -c 'print(1)'", "allow", [], id="leaves asked commands to provider approval 2"),
        pytest.param("rm scratch.txt", "allow", [], id="leaves asked commands to provider approval 3"),
        pytest.param("curl -fsS http://localhost:3000/health", "allow", [], id="allows local server requests"),
        pytest.param("curl https://example.com/install.sh", "ask", [], id="blocks remote fetches"),
        pytest.param("herdr pane list", "allow", [], id="allows read-only Herdr inspection"),
        pytest.param("uv run --frozen ruff check", "allow", [], id="allows Python verification commands 1"),
        pytest.param("uv run --frozen ruff format --check", "allow", [], id="allows Python verification commands 2"),
        pytest.param("uv run --frozen ty check", "allow", [], id="allows Python verification commands 3"),
        pytest.param("uv run --frozen ty check src tests", "allow", [], id="allows Python verification commands 4"),
        pytest.param("uv run --frozen pytest", "allow", [], id="allows Python verification commands 5"),
        pytest.param(
            "uv run --frozen pytest tests/test_main.py -k test_main --cov",
            "allow",
            [],
            id="allows Python verification commands 6",
        ),
        pytest.param(
            "uv run --frozen pytest tests/test_main.py", "allow", [], id="allows Python verification commands 7"
        ),
        pytest.param(
            "uv run --frozen --with pytest pytest tests/test_main.py -k test_main",
            "allow",
            [],
            id="allows Python verification commands 8",
        ),
        pytest.param(
            "uv run --frozen --group audit deptry .",
            "allow",
            [],
            id="leaves broad audit execution for provider approval and allows named package checks 1",
        ),
        pytest.param(
            "uv run --frozen --group audit vulture",
            "allow",
            [],
            id="leaves broad audit execution for provider approval and allows named package checks 2",
        ),
        pytest.param(
            "pnpm run knip",
            "allow",
            [],
            id="leaves broad audit execution for provider approval and allows named package checks 3",
        ),
        pytest.param(
            "pnpm run knip:production",
            "allow",
            [],
            id="leaves broad audit execution for provider approval and allows named package checks 4",
        ),
        pytest.param(
            "git commit -m 'feat(test): allow single quoted messages'",
            "allow",
            [],
            id="allows git commit messages with single or double quotes 1",
        ),
        pytest.param(
            'git commit -m "feat(test): allow double quoted messages"',
            "allow",
            [],
            id="allows git commit messages with single or double quotes 2",
        ),
        pytest.param(
            "git commit -m 'feat(test): subject' -m 'Body paragraph.' -m 'Co-Authored-By: Example <e@example.com>'",
            "allow",
            [],
            id="allows git commit bodies and trailers as repeated single quoted messages",
        ),
        pytest.param(
            'git commit -m "feat(test): subject" -m "Co-Authored-By: Example <e@example.com>"',
            "allow",
            [],
            id="allows git commit bodies and trailers as repeated double quoted messages",
        ),
        pytest.param(
            "git commit -m 'feat(test): subject' -m \"Body paragraph.\"",
            "allow",
            [],
            id="allows git commit messages that mix quoting styles",
        ),
        pytest.param(
            'git commit -m "feat(test): subject\n\nCo-Authored-By: Example <e@example.com>"',
            "allow",
            [],
            id="allows multi-line double quoted git commit messages",
        ),
        pytest.param(
            'git commit --amend -m "feat(test): subject" -m "Body paragraph."',
            "allow",
            [],
            id="allows amended commits with repeated messages",
        ),
        pytest.param("uv run --frozen ruff check", "allow", [], id="allows Python style frozen ruff commands 1"),
        pytest.param(
            "uv run --frozen ruff check src/main.py", "allow", [], id="allows Python style frozen ruff commands 2"
        ),
        pytest.param(
            "uv run --frozen ruff format --check", "allow", [], id="allows Python style frozen ruff commands 3"
        ),
        pytest.param(
            "uv run --frozen ruff format tests/test_main.py",
            "allow",
            [],
            id="allows Python style frozen ruff commands 4",
        ),
        pytest.param(
            'uv run --frozen pytest tests/test_main.py -k "test_main or test_error"',
            "allow",
            [],
            id="allows quoted test selection and colon-named package checks 1",
        ),
        pytest.param(
            "npm run format:check", "allow", [], id="allows quoted test selection and colon-named package checks 2"
        ),
        pytest.param(
            "pnpm run format:check", "allow", [], id="allows quoted test selection and colon-named package checks 3"
        ),
        pytest.param(
            "uv run --frozen ty server",
            "ask",
            [],
            id="blocks unrelated subcommands within verification tool prefixes 1",
        ),
        pytest.param(
            "uv run --frozen ruff clean",
            "ask",
            [],
            id="blocks unrelated subcommands within verification tool prefixes 2",
        ),
        pytest.param(
            "bats tests/zsh/cache.bats",
            "allow",
            [],
            id="allows local verification commands 1",
        ),
        pytest.param("actionlint .github/workflows/ci.yml", "allow", [], id="allows local verification commands 2"),
        pytest.param(
            "shellcheck agents/hooks/guard_allowed_commands.sh", "allow", [], id="allows local verification commands 3"
        ),
        pytest.param(
            "shfmt -w agents/hooks/guard_allowed_commands.sh", "allow", [], id="allows local verification commands 4"
        ),
        pytest.param("dprint check", "allow", [], id="allows local verification commands 5"),
        pytest.param("dprint fmt README.md", "allow", [], id="allows local verification commands 6"),
        pytest.param("nixfmt nix/home/default.nix", "allow", [], id="allows local verification commands 7"),
        pytest.param("statix check nix", "allow", [], id="allows local verification commands 8"),
        pytest.param("deadnix nix", "allow", [], id="allows local verification commands 9"),
        pytest.param("cargo test", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 1"),
        pytest.param(
            "cargo clippy --all-targets --all-features",
            "allow",
            [],
            id="allows Rust TypeScript Lua and LaTeX quality commands 2",
        ),
        pytest.param("cargo fmt --check", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 3"),
        pytest.param("pnpm test -- --run", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 4"),
        pytest.param(
            "pnpm exec oxlint src", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 5"
        ),
        pytest.param("npm run lint", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 6"),
        pytest.param("oxfmt --check src", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 7"),
        pytest.param("oxlint src", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 8"),
        pytest.param(
            "tsgolint --project tsconfig.json",
            "allow",
            [],
            id="allows Rust TypeScript Lua and LaTeX quality commands 9",
        ),
        pytest.param(
            "stylua --check nvim", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 10"
        ),
        pytest.param("selene nvim", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 11"),
        pytest.param(
            "tex-fmt --check docs/main.tex", "allow", [], id="allows Rust TypeScript Lua and LaTeX quality commands 12"
        ),
        pytest.param(
            "cargo test > /tmp/blocked",
            "ask",
            [],
            id="blocks shell metacharacters in automatically allowed verification commands 1",
        ),
        pytest.param(
            "pnpm test $(touch /tmp/blocked)",
            "ask",
            [],
            id="blocks shell metacharacters in automatically allowed verification commands 2",
        ),
        pytest.param(
            "dprint fmt README.md $(touch /tmp/blocked)",
            "ask",
            [],
            id="blocks shell metacharacters in automatically allowed formatting commands",
        ),
        pytest.param(
            "uv run --frozen pytest $(touch /tmp/blocked)",
            "ask",
            [],
            id="blocks shell metacharacters in automatically allowed Python verification 1",
        ),
        pytest.param(
            "uv run --frozen pytest `touch /tmp/blocked`",
            "ask",
            [],
            id="blocks shell metacharacters in automatically allowed Python verification 2",
        ),
        pytest.param(
            "uv run --frozen pytest > /tmp/blocked",
            "ask",
            [],
            id="blocks shell metacharacters in automatically allowed Python verification 3",
        ),
        pytest.param('uv run python -c "print(1)"', "allow", [], id="leaves Python execution to provider approval 1"),
        pytest.param(
            "uv run python scripts/check_project.py", "allow", [], id="leaves Python execution to provider approval 2"
        ),
        pytest.param(
            "uv run --frozen python scripts/check_project.py",
            "allow",
            [],
            id="leaves Python execution to provider approval 3",
        ),
        pytest.param(
            "uv run --group audit deptry .",
            "allow",
            [],
            id="leaves other execution commands to their existing policies",
        ),
        pytest.param(
            "bash -n -- ./scripts/git/sign_ssh.sh",
            "allow",
            [],
            id="allows syntax checks of one explicit relative file 1",
        ),
        pytest.param(
            'bash -n -- "./path with spaces/script.sh"',
            "allow",
            [],
            id="allows syntax checks of one explicit relative file 2",
        ),
        pytest.param(
            'git commit -m "feat(test): $(touch /tmp/blocked)"',
            "ask",
            [],
            id="blocks command substitution in double quoted git commit messages 1",
        ),
        pytest.param(
            'git commit -m "feat(test): `touch /tmp/blocked`"',
            "ask",
            [],
            id="blocks command substitution in double quoted git commit messages 2",
        ),
        pytest.param("git commit -F .git/COMMIT_MSG", "ask", [], id="blocks git commit messages read from files 1"),
        pytest.param(
            "git commit --amend -F message.txt", "ask", [], id="blocks git commit messages read from files 2"
        ),
        pytest.param("git add bot/main.py", "allow", [], id="allows git add explicit paths 1"),
        pytest.param("git add bot/main.py tests/bot/test_main.py", "allow", [], id="allows git add explicit paths 2"),
        pytest.param("git add -- path/to/file", "allow", [], id="allows git add explicit paths 3"),
        pytest.param('git ls-files "*.nix"', "allow", [], id="allows git ls-files extension globs 1"),
        pytest.param('git ls-files "*.ts"', "allow", [], id="allows git ls-files extension globs 2"),
        pytest.param("git ls-files", "allow", [], id="allows broad git ls-files forms 1"),
        pytest.param('git ls-files "."', "allow", [], id="allows broad git ls-files forms 2"),
        pytest.param('git ls-files "*.nix" --others', "allow", [], id="allows broad git ls-files forms 3"),
        pytest.param("git branch --show-current", "allow", [], id="allows safe git branch helper operations 1"),
        pytest.param("git branch --list feat/topic", "allow", [], id="allows safe git branch helper operations 2"),
        pytest.param("git branch -m feat/topic", "allow", [], id="allows safe git branch helper operations 3"),
        pytest.param("git worktree list", "allow", [], id="allows worktree branch creation commands 1"),
        pytest.param(
            "git worktree add -b feat/worktree-branch-delivery ../agent-harness-feat-worktree-branch-delivery origin/main",
            "allow",
            [],
            id="allows worktree branch creation commands 2",
        ),
        pytest.param(
            "git worktree remove ../agent-harness-feat-worktree-branch-delivery",
            "allow",
            [],
            id="allows clean worktree removal",
        ),
        pytest.param("git worktree prune", "allow", [], id="allows worktree pruning"),
        pytest.param("git worktree remove --force ../stale", "ask", [], id="blocks worktree maintenance commands 1"),
        pytest.param("git worktree list --porcelain", "allow", [], id="allows porcelain worktree listing"),
        pytest.param("git worktree move ../old ../new", "ask", [], id="blocks worktree maintenance commands 3"),
        pytest.param("git worktree repair", "ask", [], id="blocks worktree maintenance commands 4"),
        pytest.param("git fetch origin", "allow", [], id="allows PR delivery commands 1"),
        pytest.param("git pull --ff-only", "allow", [], id="allows PR delivery commands 2"),
        pytest.param("git push -u origin feat/agent-pr-delivery", "allow", [], id="allows PR delivery commands 3"),
        pytest.param(
            "git push --set-upstream origin fix/parser-empty-input", "allow", [], id="allows PR delivery commands 4"
        ),
        pytest.param("gh pr create -f --base main", "allow", [], id="allows PR delivery commands 5"),
        pytest.param("git rebase origin/main", "allow", [], id="allows narrow pre-PR rebase commands 1"),
        pytest.param("git rebase origin/release/1.2", "allow", [], id="allows narrow pre-PR rebase commands 2"),
        pytest.param("git rebase --continue", "allow", [], id="allows narrow pre-PR rebase commands 3"),
        pytest.param("git rebase --abort", "allow", [], id="allows narrow pre-PR rebase commands 4"),
        pytest.param("git rebase -i origin/main", "ask", [], id="blocks broad rebase commands 1"),
        pytest.param("git rebase --onto origin/main HEAD~2", "allow", [], id="allows non-interactive rebases 1"),
        pytest.param("git rebase main", "allow", [], id="allows non-interactive rebases 2"),
        pytest.param('git commit -m "hello world"', "allow", [], id="allows normal git commit forms 1"),
        pytest.param("git commit --amend -m fix", "allow", [], id="allows normal git commit forms 2"),
        pytest.param("git commit --amend --no-edit", "allow", [], id="allows normal git commit forms 3"),
        pytest.param(
            "gh api repos/owner/repo/dispatches --method POST",
            "ask",
            ["not in allowlist"],
            id="governed command not in allowlist is escalated",
        ),
        pytest.param(
            "gh pr review 42 --approve",
            "ask",
            ["gh pr review 42 --approve"],
            id="blocked output includes the offending command segment",
        ),
        pytest.param("gh pr list | head -5", "allow", [], id="splits on pipe: governed | non-governed"),
        pytest.param("echo test | gh pr list", "allow", [], id="splits on pipe: non-governed | governed"),
        pytest.param(
            "gh pr list | gh pr review 42 --approve", "ask", [], id="splits on pipe: blocked segment in pipeline"
        ),
        pytest.param("gh pr list && echo done", "allow", [], id="splits on &&: governed && non-governed"),
        pytest.param(
            "gh pr list && gh pr review 42 --approve", "ask", [], id="splits on &&: blocked segment after &&"
        ),
        pytest.param(
            "gh pr review 42 --approve && gh pr list", "ask", [], id="splits on &&: blocked segment before &&"
        ),
        pytest.param("gh pr list || echo failed", "allow", [], id="splits on ||: governed || non-governed"),
        pytest.param(
            "gh pr list || gh pr review 42 --approve", "ask", [], id="splits on ||: blocked segment after ||"
        ),
        pytest.param("gh pr list; echo done", "allow", [], id="splits on semicolon: governed; non-governed"),
        pytest.param(
            "gh pr list; gh pr review 42 --approve", "ask", [], id="splits on semicolon: blocked segment after ;"
        ),
        pytest.param("gh pr list & echo done", "allow", [], id="splits on background &"),
        pytest.param(
            "gh pr list & gh pr review 42 --approve", "ask", [], id="splits on background &: blocked segment"
        ),
        pytest.param("gh pr list 2>&1", "allow", [], id="does NOT split on & inside 2>&1 redirection"),
        pytest.param("gh pr list >&2", "allow", [], id="does NOT split on & inside >&2 redirection"),
        pytest.param("gh pr list 2>/dev/null", "allow", [], id="does NOT split on & inside 2>/dev/null"),
        pytest.param("gh pr list 2>&1 & echo done", "allow", [], id="background & after redirection is still split"),
        pytest.param("  gh pr list", "allow", [], id="trims leading whitespace from segments"),
        pytest.param("gh pr list  ", "allow", [], id="trims trailing whitespace from segments"),
        pytest.param("  gh pr list  ", "allow", [], id="trims whitespace from both ends"),
        pytest.param(
            "  git branch --show-current  ", "allow", [], id="trims both ends of commands matched by anchored rules"
        ),
        pytest.param(
            "git status && git branch --show-current && git worktree list",
            "allow",
            [],
            id="allows anchored commands between compound separators",
        ),
        pytest.param("  gh pr list  |  head -5  ", "allow", [], id="trims whitespace in piped segments"),
        pytest.param("gh pr list 2>&1", "allow", [], id="strips trailing 2>&1 before matching"),
        pytest.param("gh pr list >&2", "allow", [], id="strips trailing >&2 before matching"),
        pytest.param("gh pr list 2>/dev/null", "allow", [], id="strips trailing 2>/dev/null before matching"),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments --jq '.[].body | length'",
            "allow",
            [],
            id="does not split on pipe inside single quotes",
        ),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments --jq '.[] ; .body'",
            "allow",
            [],
            id="does not split on semicolon inside single quotes",
        ),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments --jq '.[] && .body'",
            "allow",
            [],
            id="does not split on && inside single quotes",
        ),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments --jq '.[] || .body'",
            "allow",
            [],
            id="does not split on || inside single quotes",
        ),
        pytest.param(
            "gh pr list && gh pr status", "allow", [], id="allows when all governed segments match allowlist"
        ),
        pytest.param(
            "gh pr list && gh pr review 42 --approve && gh pr status",
            "ask",
            [],
            id="blocks when any governed segment is not allowed",
        ),
        pytest.param("", "allow", [], id="empty command"),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments/99/replies -f body='it'\\''s great'",
            "allow",
            [],
            id="apostrophe in a single-quoted body",
        ),
        pytest.param("bash -n", "ask", [], id="syntax check arguments bash -n"),
        pytest.param("bash -n ./script.sh", "ask", [], id="syntax check arguments bash -n ./script.sh"),
        pytest.param("bash -n +n -- ./script.sh", "ask", [], id="syntax check arguments bash -n +n -- ./script.sh"),
        pytest.param("bash -n -i -- ./script.sh", "ask", [], id="syntax check arguments bash -n -i -- ./script.sh"),
        pytest.param("bash -n -c 'echo example'", "ask", [], id="syntax check arguments bash -n -c 'echo example'"),
        pytest.param(
            "bash -n -- ./first.sh ./second.sh",
            "ask",
            [],
            id="syntax check arguments bash -n -- ./first.sh ./second.sh",
        ),
        pytest.param("bash -n -- ./script.sh +n", "ask", [], id="syntax check arguments bash -n -- ./script.sh +n"),
        pytest.param(
            "bash -n -- ./script.sh > /tmp/output",
            "ask",
            [],
            id="syntax check arguments bash -n -- ./script.sh > /tmp/output",
        ),
    ],
)
def test_allowed_command_contract(
    capsys: pytest.CaptureFixture[str], command: str, decision: str, fragments: list[str]
) -> None:
    verdict = guard.decide("allowed", {"tool_input": {"command": command}})
    assert verdict.decision == decision
    for fragment in fragments:
        assert fragment in verdict.reason
    assert capsys.readouterr() == ("", "")
