"""Allowed-command contracts inspect text without executing the submitted commands."""

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
pytestmark = pytest.mark.usefixtures("isolated_project")


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(
            'git commit -S -m "style: subject" -m "Body line one\nline two." -m "Refs #18" 2>&1 | head -40',
            id="git commit in any form",
        ),
        pytest.param("git commit -F .git/COMMIT_MSG", id="git commit messages read from files"),
        pytest.param('git commit -m "feat: $(cat subject.txt)"', id="git commit messages built at run time"),
        pytest.param("git branch -r --contains abc1234", id="git branch in any form"),
        pytest.param("git rebase -i origin/main", id="interactive git forms"),
        pytest.param("git config user.name example", id="git configuration the sandbox confines"),
        pytest.param("git -c core.fsmonitor=false switch main --force", id="forms the Git guard judges"),
        pytest.param('W=/tmp/x; git -C $W add src/main.py && git -C "$W" diff', id="run-time words in local git"),
        pytest.param("sed -i '' -E 's/^  final: .*,$/  final: 0.61,/' src/engine/parameters.ts", id="in-place edits"),
        pytest.param("D=/tmp/x; mkdir -p $D && cat > $D/pr.md <<'EOF'\n## Summary\nEOF", id="run-time file targets"),
        pytest.param('for f in "0.55:0.85" "0.57:0.85"; do echo "${f%%:*}"; done', id="parameter expansions"),
        pytest.param("cp *.md backup/", id="globs"),
        pytest.param('for c in $(git rev-list main..HEAD); do printf "%s " ${c:0:7}; done', id="parameter operations"),
        pytest.param("cd $DIR && ls", id="run-time directories"),
        pytest.param("$CMD --help", id="run-time program names, which the Git guard judges"),
        pytest.param("pnpm test $(touch /tmp/scratch)", id="substitutions of local commands"),
        pytest.param("uv run --frozen ty server", id="unlisted subcommands of approved tools"),
        pytest.param("pnpm install --frozen-lockfile --prefer-offline", id="unlisted flags of approved tools"),
        pytest.param("bash -n -- ./first.sh ./second.sh", id="unlisted shell syntax checks"),
        pytest.param("python3 - <<'EOF'\nprint(1)\nEOF", id="interpreters"),
        pytest.param("git push --force-with-lease origin feat/example", id="push forms the Git guard judges"),
        pytest.param("gh pr list", id="listed GitHub forms"),
        pytest.param("/opt/homebrew/bin/gh pr list", id="listed GitHub forms invoked by path"),
        pytest.param("gh pr view $NUMBER --json state", id="run-time words in listed GitHub forms"),
        pytest.param('gh pr create --head topic --body-file "$D/pr.md"', id="run-time body files"),
        pytest.param("gh pr review 42 --comment -b 'Looks good'", id="reviewable GitHub operations 1"),
        pytest.param("gh pr close 42", id="reviewable GitHub operations 2"),
        pytest.param("gh run rerun 123", id="reviewable GitHub operations 3"),
        pytest.param("gh api user", id="GitHub reads 1"),
        pytest.param("gh api repos/furedea/$r/dependabot/alerts --jq '.[] | .number'", id="GitHub reads at run time"),
        pytest.param("gh api repos/owner/repo/pulls/1/comments --jq '.[] | .body'", id="GitHub reads 2"),
        pytest.param("gh api '/advisories?ecosystem=pip&affects=urllib3' --jq '.[] | .summary'", id="GitHub reads 3"),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments/99/replies -f body='it'\\''s great'",
            id="apostrophe in a single-quoted body",
        ),
        pytest.param("gh stack submit --auto", id="non-interactive stack commands"),
        pytest.param("gh pr list 2>&1 | head -5", id="GitHub forms in pipelines"),
        pytest.param("curl -fsS http://localhost:3000/health", id="local server requests"),
        pytest.param("", id="empty command"),
    ],
)
def test_commands_whose_effects_the_checks_can_see_pass(capsys: pytest.CaptureFixture[str], command: str) -> None:
    assert guard.decide("allowed", {"tool_input": {"command": command}}).decision == "allow"
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "command,fragments",
    [
        pytest.param("gh pr review 42 --approve", ["gh pr review 42 --approve"], id="unlisted GitHub forms"),
        pytest.param("env gh pr review 42 --approve", ["gh pr review 42 --approve"], id="behind env"),
        pytest.param("command gh pr review 42 --approve", [], id="behind the command builtin"),
        pytest.param("/opt/homebrew/bin/gh pr review 42 --approve", [], id="invoked by path"),
        pytest.param("gh pr list && gh pr review 42 --approve", [], id="after a listed form"),
        pytest.param("gh pr review 42 --approve | head", [], id="inside a pipeline"),
        pytest.param("for n in 1 2; do gh pr review $n --approve; done", [], id="inside a loop"),
        pytest.param("gh api repos/owner/repo/issues/1 --method DELETE", ["not in allowlist"], id="GitHub API writes"),
        pytest.param("gh api repos/owner/repo/dispatches --method POST", [], id="GitHub API dispatches"),
        pytest.param("gh api $ENDPOINT --method DELETE", [], id="GitHub API writes at run-time endpoints"),
        pytest.param(
            "gh api repos/owner/repo/issues -f title=$TITLE", [], id="GitHub API writes with run-time fields"
        ),
        pytest.param("gh stack init", ["gh stack init"], id="interactive stack commands 1"),
        pytest.param("gh stack submit", ["gh stack submit"], id="interactive stack commands 2"),
        pytest.param("curl https://example.com/install.sh", [], id="remote fetches"),
    ],
)
def test_unlisted_forms_of_commands_that_reach_github_or_the_network_ask(
    capsys: pytest.CaptureFixture[str], command: str, fragments: list[str]
) -> None:
    verdict = guard.decide("allowed", {"tool_input": {"command": command}})
    assert verdict.decision == "ask"
    for fragment in fragments:
        assert fragment in verdict.reason
    assert capsys.readouterr() == ("", "")
