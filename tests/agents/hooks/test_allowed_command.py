"""Allowed-command contracts inspect text without executing the submitted commands."""

import pytest

from tests.runtime import load_script_module


guard = load_script_module("agents/hooks/guard_command.py", "guard_command")
pytestmark = pytest.mark.usefixtures("isolated_project")


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(
            'git commit -m "style: subject" -m "Body line one\nline two." -m "Refs #18" 2>&1 | head -40',
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
        pytest.param(
            "gh pr create --head topic --title 'fix: x' --body \"$(cat <<'EOF'\nUse `git add -A` never.\n$HOME stays.\nEOF\n)\"",
            id="PR bodies inline through a quoted heredoc",
        ),
        pytest.param("gh pr review 42 --comment -b 'Looks good'", id="reviewable GitHub operations 1"),
        pytest.param("gh pr close 42", id="reviewable GitHub operations 2"),
        pytest.param("gh run rerun 123", id="reviewable GitHub operations 3"),
        pytest.param("gh api user", id="GitHub reads 1"),
        pytest.param(
            "gh api 'search/code?q=%22struct+X%22+repo:openai/codex' --jq '.items[].path'", id="GitHub searches"
        ),
        pytest.param(
            "gh api repos/o/r/actions/runs --paginate -H 'Accept: application/json'", id="GitHub reads with headers"
        ),
        pytest.param(
            "gh api 'repos/openai/codex/contents/a.rs?ref=rust-v0.163.0' --jq .content", id="GitHub reads with bare jq"
        ),
        pytest.param("gh api repos/furedea/$r/dependabot/alerts --jq '.[] | .number'", id="GitHub reads at run time"),
        pytest.param("gh api repos/owner/repo/pulls/1/comments --jq '.[] | .body'", id="GitHub reads 2"),
        pytest.param("gh api '/advisories?ecosystem=pip&affects=urllib3' --jq '.[] | .summary'", id="GitHub reads 3"),
        pytest.param(
            "gh api repos/owner/repo/pulls/1/comments/99/replies -f body='it'\\''s great'",
            id="apostrophe in a single-quoted body",
        ),
        pytest.param("gh api graphql -f query='query { viewer { login } }'", id="GitHub GraphQL queries"),
        pytest.param(
            'gh api graphql -f "query=query { repository(owner: \\"o\\", name: \\"r\\") { id } }"',
            id="GitHub GraphQL queries in double quotes",
        ),
        pytest.param("gh stack submit --auto", id="non-interactive stack commands"),
        pytest.param("gh pr list 2>&1 | head -5", id="GitHub forms in pipelines"),
        pytest.param("curl -fsS http://localhost:3000/health", id="local server requests"),
        pytest.param("curl -s https://pypi.org/pypi/mutmut/json", id="remote fetches"),
        pytest.param(
            "curl -fsSL -o pkg.tgz -H 'User-Agent: x' https://registry.npmjs.org/a/-/a-1.tgz", id="remote downloads"
        ),
        pytest.param(
            'curl -s -o /dev/null -w "%{http_code}\\n" -X HEAD https://cdn.example.com/v1/a.tar.gz',
            id="remote status probes",
        ),
        pytest.param("wget -q -O - https://example.com/install.sh", id="remote fetches with wget"),
        pytest.param(
            "wget -qO- --timeout=10 --header 'Accept: x' https://example.com/a", id="wget clusters and values"
        ),
        pytest.param("curl -sSo out.html -H 'Accept: text/html' https://example.com/", id="curl clusters with values"),
        pytest.param("curl -X POST -d '{\"a\": 1}' http://127.0.0.1:8080/api", id="local server writes"),
        pytest.param(
            'gh api -H "Accept: application/vnd.github.raw" "repos/o/r/contents/a.nix?ref=v1" | sed -n 1,20p',
            id="GitHub reads with a header before the endpoint",
        ),
        pytest.param(
            "gh api --header 'X-GitHub-Api-Version: 2022-11-28' repos/o/r/releases --jq '.[].tag_name'",
            id="GitHub reads with a version header",
        ),
        pytest.param("herdr agent read lane-a --source recent --lines 80", id="Herdr agent reads"),
        pytest.param("herdr agent wait lane-a --until done --until blocked --timeout 600000", id="Herdr agent waits"),
        pytest.param("herdr worktree list --cwd /repo", id="Herdr worktree lists"),
        pytest.param("herdr agent read --help", id="Herdr help for the lane commands"),
        pytest.param(
            "herdr worktree open --cwd /repo --branch feat/x --label x --no-focus", id="Herdr worktree opens"
        ),
        pytest.param('t(){ uv run --frozen pytest -q "$@"; }; t tests/a.py && t tests/b.py', id="local functions"),
        pytest.param(
            'c(){ msg="$1"; shift; git add -- "$@" && git commit -q -m "$msg"; }; c \'fix: x\' a.py',
            id="functions with positional parameters",
        ),
        pytest.param("herdr pane list", id="Herdr reads"),
        pytest.param(
            "herdr worktree create --cwd /repo --branch feat/lane-a --base origin/main --label 'lane a' --no-focus",
            id="Herdr task worktrees",
        ),
        pytest.param("herdr pane split --pane w1:p2 --direction right --cwd $W --no-focus", id="Herdr panes"),
        pytest.param("herdr agent start lane-a --kind claude --pane w1:p2", id="Herdr Claude agents"),
        pytest.param("herdr agent start lane-b --pane w1:p3 --kind codex --timeout 60000", id="Herdr Codex agents"),
        pytest.param(
            'herdr agent prompt lane-a "Implement #181.\nRead the plan first." --wait --timeout 120000',
            id="Herdr prompts",
        ),
        pytest.param('herdr agent prompt lane-a "$(cat $D/brief.md)"', id="Herdr prompts built at run time"),
        pytest.param(
            "gh pr edit 242 --body \"$(printf '%s' 'pass ${a[@]} or \"$@\" or $1 through')\"",
            id="expansion text inside a substituted body",
        ),
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
        pytest.param("curl -d @notes.txt https://example.com/upload", [], id="remote posts"),
        pytest.param("curl --data-binary @a https://example.com/", [], id="remote binary posts"),
        pytest.param("curl -F file=@a https://example.com/", [], id="remote form uploads"),
        pytest.param("curl -T a https://example.com/", [], id="remote uploads"),
        pytest.param("curl -X POST https://example.com/", [], id="remote non-GET methods"),
        pytest.param("curl -sX DELETE https://example.com/", [], id="remote methods in a flag cluster"),
        pytest.param("curl --json '{}' https://example.com/", [], id="remote JSON posts"),
        pytest.param("curl -K config.txt https://example.com/", [], id="remote options from a file"),
        pytest.param("curl -fsSd x=1 https://example.com/", [], id="remote data in a flag cluster"),
        pytest.param("curl -s $URL", [], id="remote fetches of run-time words"),
        pytest.param("curl -s https://example.com/ -o $OUT", [], id="remote fetches with run-time options"),
        pytest.param("wget --post-data x=1 https://example.com/", [], id="wget posts"),
        pytest.param("gh api -X PATCH repos/o/r -f a=b", [], id="GitHub API writes with -X"),
        pytest.param(
            "gh api -H 'X-HTTP-Method-Override: DELETE' repos/o/r/issues/1", [], id="GitHub method override headers"
        ),
        pytest.param("gh api -H 'Accept: x' repos/o/r/issues --input body.json", [], id="GitHub API input bodies"),
        pytest.param("herdr worktree open --cwd /repo --path /w --trust-repository", [], id="Herdr open with trust"),
        pytest.param("herdr worktree list --trust-repository", [], id="Herdr list with trust"),
        pytest.param("f(){ gh pr review 42 --approve; }; f", [], id="inside a function body"),
        pytest.param("curl '-d' @f https://example.com/", [], id="send options in single quotes"),
        pytest.param('curl "-d" @f https://example.com/', [], id="send options in double quotes"),
        pytest.param("curl \\-d @f https://example.com/", [], id="send options escaped"),
        pytest.param("wget '--post-file=f' https://example.com/", [], id="wget send options in quotes"),
        pytest.param("gh api '-XDELETE' repos/o/r/issues/1", [], id="GitHub methods in quotes"),
        pytest.param(
            'f(){ gh api "$@"; }; f -X DELETE repos/o/r/issues/1', [], id="functions forwarding all arguments"
        ),
        pytest.param(
            "f(){ curl $*; }; f -d @a https://example.com/", [], id="functions forwarding unquoted arguments"
        ),
        pytest.param(
            'f(){ gh api "$1" "$2"; }; f -XDELETE repos/o/r', [], id="functions forwarding positional arguments"
        ),
        pytest.param('gh api "${args[@]}"', [], id="array expansions"),
        pytest.param("curl -H @headers.txt https://example.com/", [], id="headers read from a file"),
        pytest.param("curl --header @- https://example.com/", [], id="headers read from input"),
        pytest.param("curl -sH '@h' https://example.com/", [], id="quoted headers read from a file"),
        pytest.param("printf '%s\\n' -d @notes.txt | xargs curl https://pypi.org/", [], id="curl options from xargs"),
        pytest.param("echo -X DELETE | xargs gh api repos/o/r/issues/1", [], id="gh api options from xargs"),
        pytest.param("xargs wget https://example.com/ < urls.txt", [], id="wget options from xargs"),
        pytest.param("curl -H \\@headers.txt https://pypi.org/", [], id="headers read from an escaped file name"),
        pytest.param("curl -H 'Accept: '$TYPE https://example.com/", [], id="run-time header values"),
        pytest.param("curl --data-urlencode q=x https://example.com/", [], id="options outside the read-only list"),
        pytest.param("curl --max-time=5 https://example.com/", [], id="attached long option values"),
        pytest.param("gh api graphql -f query='mutation { x }'", [], id="GitHub GraphQL mutations"),
        pytest.param("curl -d{} https://example.com/", [], id="send options that need quoting"),
        pytest.param("curl -sd'a b' https://example.com/", [], id="send options with spaces in a cluster"),
        pytest.param("curl --data 'a b' https://example.com/", [], id="long send options with spaces"),
        pytest.param("wget '--post-data=a b' https://example.com/", [], id="wget send options that need quoting"),
        pytest.param("wget --post-data '{}' https://example.com/", [], id="wget send options with a separate value"),
        pytest.param("wget -e use_proxy=on https://example.com/", [], id="wget commands"),
        pytest.param("curl -X 'GET -d x' https://example.com/", [], id="methods with spaces"),
        pytest.param("curl -o", [], id="an option without its value"),
        pytest.param('gh api repos/o/r/issues/1 --jq .x -"X" DELETE', [], id="GitHub options decoded from quotes"),
        pytest.param("f(){ curl -d @a https://example.com/; }", [], id="inside a function that is never called"),
        pytest.param("herdr worktree create --cwd /repo --trust-repository", [], id="Herdr repository trust"),
        pytest.param("herdr pane split --pane w1:p2 --env CLAUDE_CONFIG_DIR=/tmp/x", [], id="Herdr pane environments"),
        pytest.param("herdr agent start lane-a --kind gemini --pane w1:p2", [], id="Herdr agents without our hooks"),
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


def test_commit_messages_inline_through_a_quoted_heredoc_pass() -> None:
    command = "git commit -m \"$(cat <<'EOF'\nfix: don't run `rm -rf $HOME`\n\nBody.\nEOF\n)\""
    for kind in ("allowed", "forbidden"):
        assert guard.decide(kind, {"tool_input": {"command": command}}).decision == "allow"
