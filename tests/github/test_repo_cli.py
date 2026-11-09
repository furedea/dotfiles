"""Repository CLI contracts; every remote command is an isolated process fake."""

import json
import os
from pathlib import Path
import subprocess

import pytest

from tests.runtime import CliRunner, REPO_ROOT, StubWriter


SCRIPT = "github/repo.py"


@pytest.fixture
def remote(tmp_path: Path, executable: StubWriter, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("REPO_FIXTURE", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    executable(
        "ghq",
        """
        import os, sys
        from pathlib import Path
        assert sys.argv[1:] == ["root"]
        print(Path(os.environ["REPO_FIXTURE"]) / "ghq")
    """,
    )
    executable(
        "gh",
        """
        import json, os, sys
        from pathlib import Path
        root = Path(os.environ["REPO_FIXTURE"])
        args = sys.argv[1:]
        with (root / "gh.jsonl").open("a") as stream:
            stream.write(json.dumps(args) + "\\n")
        if args[:2] == ["api", "user"]:
            print("furedea")
        elif args[:2] == ["repo", "list"]:
            print(os.environ.get("GH_REPOSITORIES", ""))
        elif args[:2] == ["repo", "clone"]:
            destination = Path(args[3])
            (destination / ".git").mkdir(parents=True)
            (destination / "src").mkdir()
            (destination / "Cargo.toml").write_text('[package]\\nname = "template-rust"\\nversion = "0.1.0"\\nedition = "2024"\\n')
            (destination / "go.mod").write_text("module github.com/furedea/template-go\\n\\ngo 1.24\\n")
            for name in ("flake.nix", ".envrc", "src/main.rs"):
                (destination / name).touch()
        elif args[0] == "api" and "/git/ref/heads/" in args[1]:
            ready = root / "ref-ready"
            if os.environ.get("GH_REF_EMPTY_ONCE") == "1" and not ready.exists():
                ready.touch()
                print('{"message":"Git Repository is empty.","status":"409"}')
                sys.exit(1)
            print("refs/heads/main")
        elif args[0] == "api" and ".default_branch // empty" in args:
            print("main")
        elif args[0] == "api" and ".visibility" in args:
            print(os.environ.get("GH_VISIBILITY", "public"))
        elif args[0] == "api" and args[1].endswith("/code-scanning/default-setup") and "-X" not in args:
            print(os.environ.get("GH_CODEQL_STATE", "not-configured"))
        elif args[0] == "api" and "/code-scanning/analyses" in args[1]:
            if os.environ.get("GH_ANALYSES_MISSING") == "1":
                print('{"message":"no analysis found","status":"404"}')
                sys.exit(1)
            print(os.environ.get("GH_CODEQL_ANALYSIS_KEYS", ""))
        elif args[0] == "api" and "/contents/.github/workflows/" in args[1]:
            print(os.environ.get("GH_WORKFLOW_CONTENT", "name: ci"))
        elif args[0] == "api" and "/actions/workflows" in args[1]:
            print(os.environ.get("GH_ACTIVE_WORKFLOWS", ""))
        elif args[0] == "api" and args[1].endswith("/code-scanning/default-setup") and os.environ.get("GH_CODEQL_FAILURE") == "1":
            print("HTTP 422", file=sys.stderr)
            sys.exit(1)
        elif args[0] == "api" and args[1].endswith("/rulesets") and "--jq" in args:
            print(os.environ.get("GH_RULESET_ID", ""))
        elif args[:2] == ["repo", "create"] or (args[0] == "api" and "-X" in args):
            pass
        else:
            sys.exit("unexpected gh arguments: " + repr(args))
    """,
    )
    executable(
        "git",
        """
        import json, os, sys
        from pathlib import Path
        root = Path(os.environ["REPO_FIXTURE"])
        args = sys.argv[1:]
        with (root / "git.jsonl").open("a") as stream:
            stream.write(json.dumps(args) + "\\n")
        assert args[0] == "-C" and args[2:] == ["pull", "--ff-only"]
        if os.environ.get("GIT_PULL_FAILURE", "__never__") in args[1]:
            sys.exit(1)
    """,
    )
    executable("sleep", "")
    return tmp_path


def calls(root: Path, tool: str = "gh") -> list[list[str]]:
    path = root / f"{tool}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.mark.parametrize(
    "arguments,fragment",
    [
        (("--help",), "repo <command> [arguments]"),
        (("-h",), "repo <command> [arguments]"),
        (("create",), "Usage:"),
        (("create", "--help"), "repo create <name-or-owner/name> <visibility> [options]"),
        (("create", "agent-harness", "--private", "-h"), "Usage:"),
        (("configure",), "Usage:"),
        (("configure", "--help"), "repo configure <name-or-owner/name>"),
        (("configure", "-h"), "Usage:"),
        (("configure", "--unknown"), "Usage:"),
        (("configure", "owner/first", "owner/second"), "Usage:"),
    ],
)
def test_help_and_invalid_arguments_do_not_contact_remote(
    run_cli: CliRunner, remote: Path, arguments: tuple[str, ...], fragment: str
) -> None:
    result = run_cli(SCRIPT, *arguments)
    assert result.returncode == 1
    assert fragment in result.stderr
    assert result.stdout == ""
    assert not calls(remote)
    assert not any(line.startswith("+") for line in result.stderr.splitlines())
    if arguments == ("--help",):
        assert all(name in result.stderr for name in ("create", "configure", "sync"))
    if arguments == ("create", "--help"):
        assert all(name in result.stderr for name in ("--template", "--private", "--clone"))


@pytest.mark.parametrize("flag", ["--clone", "-c", "--source=.", "-s=.", "--push", "--remote=origin", "-r=origin"])
def test_rejects_local_lifecycle_flags(run_cli: CliRunner, remote: Path, flag: str) -> None:
    result = run_cli(SCRIPT, "create", "agent-harness", "--private", flag)
    assert result.returncode == 1
    assert "controls the local clone destination" in result.stderr
    assert not calls(remote)


@pytest.mark.parametrize("options", [("--template", "furedea/template-rust"), ("--public", "--private")])
def test_requires_one_visibility(run_cli: CliRunner, remote: Path, options: tuple[str, ...]) -> None:
    result = run_cli(SCRIPT, "create", "agent-harness", *options)
    assert result.returncode == 1
    assert "exactly one of --public, --private, or --internal is required" in result.stderr
    assert not calls(remote)


@pytest.mark.parametrize("template,retry", [(False, False), (True, False), (True, True)])
def test_create_output_and_template_readiness(run_cli: CliRunner, remote: Path, template: bool, retry: bool) -> None:
    options = ["--template", "furedea/template-rust"] if template else []
    result = run_cli(
        SCRIPT, "create", "agent-harness", "--private", *options, env={"GH_REF_EMPTY_ONCE": str(int(retry))}
    )
    destination = remote / "ghq/github.com/furedea/agent-harness"
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{destination}\n"
    assert "creating GitHub repo" in result.stderr
    assert not any(line.startswith("+") for line in result.stderr.splitlines())
    logged = calls(remote)
    assert ["api", "user", "--jq", ".login"] in logged
    assert ["repo", "create", "agent-harness", "--private", *options] in logged
    assert ["repo", "clone", "furedea/agent-harness", str(destination)] in logged
    assert 'name = "agent-harness"' in (destination / "Cargo.toml").read_text()
    assert "module github.com/furedea/agent-harness\n" in (destination / "go.mod").read_text()
    if template:
        assert ["api", "repos/furedea/agent-harness", "--jq", ".default_branch // empty"] in logged
        assert logged.count(["api", "repos/furedea/agent-harness/git/ref/heads/main", "--jq", ".ref // empty"]) == (
            2 if retry else 1
        )


def test_existing_destination_prevents_remote_create(run_cli: CliRunner, remote: Path) -> None:
    (remote / "ghq/github.com/furedea/agent-harness").mkdir(parents=True)
    result = run_cli(SCRIPT, "create", "agent-harness", "--private", "--template", "furedea/template-rust")
    assert result.returncode == 1
    assert "local destination already exists" in result.stderr
    assert not any(row[:2] == ["repo", "create"] for row in calls(remote))


@pytest.mark.parametrize("name,identifier", [("myrepo", ""), ("owner/myrepo", ""), ("owner/myrepo", "42")])
def test_configure_upserts_named_ruleset(run_cli: CliRunner, remote: Path, name: str, identifier: str) -> None:
    result = run_cli(SCRIPT, "configure", name, env={"GH_RULESET_ID": identifier})
    repository = name if "/" in name else f"furedea/{name}"
    assert result.returncode == 0, result.stderr
    assert "Applied repo settings to " + repository in result.stdout
    logged = calls(remote)
    assert [
        "api",
        f"repos/{repository}",
        "-X",
        "PATCH",
        "--input",
        str(REPO_ROOT / "github/repo_settings.json"),
    ] in logged
    assert ["api", f"repos/{repository}/vulnerability-alerts", "-X", "PUT"] in logged
    suffix = f"/{identifier}" if identifier else ""
    assert [
        "api",
        f"repos/{repository}/rulesets{suffix}",
        "-X",
        "PUT" if identifier else "POST",
        "--input",
        str(REPO_ROOT / "github/ruleset.json"),
    ] in logged
    assert (f"Updated ruleset {identifier} on" if identifier else "Created ruleset on") in result.stdout
    if "/" not in name:
        assert ["api", "user", "--jq", ".login"] in logged


def code_scanning_calls(root: Path, repository: str) -> list[list[str]]:
    endpoint = f"repos/{repository}/code-scanning/default-setup"
    return [row for row in calls(root) if row[:2] == ["api", endpoint] and "PATCH" in row]


def test_configure_enables_codeql_default_setup_for_public_repository(run_cli: CliRunner, remote: Path) -> None:
    result = run_cli(SCRIPT, "configure", "owner/myrepo", env={"GH_VISIBILITY": "public"})
    assert result.returncode == 0, result.stderr
    assert code_scanning_calls(remote, "owner/myrepo") == [
        [
            "api",
            "repos/owner/myrepo/code-scanning/default-setup",
            "-X",
            "PATCH",
            "-f",
            "state=configured",
            "-f",
            "query_suite=default",
        ]
    ]
    assert "Enabled CodeQL default setup on owner/myrepo" in result.stdout


@pytest.mark.parametrize("visibility", ["private", "internal"])
def test_configure_skips_codeql_default_setup_for_non_public_repository(
    run_cli: CliRunner, remote: Path, visibility: str
) -> None:
    result = run_cli(SCRIPT, "configure", "owner/myrepo", env={"GH_VISIBILITY": visibility})
    assert result.returncode == 0, result.stderr
    assert not code_scanning_calls(remote, "owner/myrepo")
    assert "Skipped CodeQL default setup on owner/myrepo" in result.stdout


SECURITY_KEY = ".github/workflows/security.yml:analyze/language:python"
DEFAULT_SETUP_KEY = "dynamic/github-code-scanning/codeql:analyze:python"
CI_WORKFLOW = ".github/workflows/ci.yml"
SECURITY_WORKFLOW = ".github/workflows/security.yml"
DEFAULT_SETUP_WORKFLOW = "dynamic/github-code-scanning/codeql"


@pytest.mark.parametrize(
    "environment,reason",
    [
        ({"GH_CODEQL_STATE": "configured"}, "already configured"),
        (
            {
                "GH_CODEQL_ANALYSIS_KEYS": SECURITY_KEY,
                "GH_ACTIVE_WORKFLOWS": f"{CI_WORKFLOW}\n{SECURITY_WORKFLOW}",
            },
            "an advanced setup is in use",
        ),
        (
            {
                "GH_ANALYSES_MISSING": "1",
                "GH_ACTIVE_WORKFLOWS": SECURITY_WORKFLOW,
                "GH_WORKFLOW_CONTENT": "uses: github/codeql-action/analyze@v3",
            },
            "an advanced setup is in use",
        ),
    ],
    ids=["configured", "active-workflow-with-analyses", "active-workflow-before-first-analysis"],
)
def test_configure_leaves_existing_codeql_setup_untouched(
    run_cli: CliRunner, remote: Path, environment: dict[str, str], reason: str
) -> None:
    result = run_cli(SCRIPT, "configure", "owner/myrepo", env=environment)
    assert result.returncode == 0, result.stderr
    assert not code_scanning_calls(remote, "owner/myrepo")
    assert f"Skipped CodeQL default setup on owner/myrepo: {reason}" in result.stdout


@pytest.mark.parametrize(
    "environment",
    [
        {"GH_CODEQL_ANALYSIS_KEYS": SECURITY_KEY, "GH_ACTIVE_WORKFLOWS": CI_WORKFLOW},
        {"GH_CODEQL_ANALYSIS_KEYS": "", "GH_ACTIVE_WORKFLOWS": f"{CI_WORKFLOW}\n{SECURITY_WORKFLOW}"},
        {"GH_ANALYSES_MISSING": "1", "GH_ACTIVE_WORKFLOWS": CI_WORKFLOW},
        {"GH_CODEQL_ANALYSIS_KEYS": DEFAULT_SETUP_KEY, "GH_ACTIVE_WORKFLOWS": DEFAULT_SETUP_WORKFLOW},
    ],
    ids=["deleted-workflow-with-old-analyses", "no-analyses", "analyses-not-found", "default-setup-own-key"],
)
def test_configure_enables_codeql_default_setup_without_an_active_advanced_workflow(
    run_cli: CliRunner, remote: Path, environment: dict[str, str]
) -> None:
    result = run_cli(SCRIPT, "configure", "owner/myrepo", env=environment)
    assert result.returncode == 0, result.stderr
    assert len(code_scanning_calls(remote, "owner/myrepo")) == 1
    assert "Enabled CodeQL default setup on owner/myrepo" in result.stdout


def test_configure_applies_ruleset_even_when_codeql_default_setup_fails(run_cli: CliRunner, remote: Path) -> None:
    result = run_cli(SCRIPT, "configure", "owner/myrepo", env={"GH_CODEQL_FAILURE": "1"})
    assert result.returncode == 0, result.stderr
    assert "warning: could not enable CodeQL default setup on owner/myrepo" in result.stderr
    assert "Created ruleset on owner/myrepo" in result.stdout
    assert any(row[:2] == ["api", "repos/owner/myrepo/rulesets"] for row in calls(remote))


@pytest.mark.parametrize(
    "existing,failure,dry_run",
    [
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (True, False, True),
    ],
)
def test_sync_processes_repositories_independently(
    run_cli: CliRunner, remote: Path, existing: bool, failure: bool, dry_run: bool
) -> None:
    owner = remote / "ghq/github.com/furedea"
    alpha, beta = owner / "alpha", owner / "beta"
    if existing:
        (alpha / ".git").mkdir(parents=True)
    result = run_cli(
        SCRIPT,
        "sync",
        *(["--dry-run"] if dry_run else []),
        env={
            "GH_REPOSITORIES": "furedea/alpha\nfuredea/beta",
            "GIT_PULL_FAILURE": "/alpha" if failure else "__never__",
        },
    )
    assert result.returncode == int(failure)
    if dry_run:
        assert not calls(remote, "git")
        assert not beta.exists()
        assert not any(row[:2] == ["repo", "clone"] for row in calls(remote))
    else:
        assert ["repo", "clone", "furedea/beta", str(beta)] in calls(remote)
        if existing:
            assert ["-C", str(alpha), "pull", "--ff-only"] in calls(remote, "git")
        else:
            assert ["repo", "clone", "furedea/alpha", str(alpha)] in calls(remote)
    assert f"[{'pull' if existing else 'clone'}] " in result.stdout
    assert f"[clone] furedea/beta -> {beta}" in result.stdout
    assert any(row[:3] == ["repo", "list", "furedea"] for row in calls(remote))


def test_sync_protects_non_git_path_and_reports_totals(run_cli: CliRunner, remote: Path) -> None:
    owner = remote / "ghq/github.com/furedea"
    (owner / "alpha/.git").mkdir(parents=True)
    (owner / "gamma").mkdir()
    marker = owner / "gamma/sentinel"
    marker.write_text("keep\n")
    result = run_cli(SCRIPT, "sync", env={"GH_REPOSITORIES": "furedea/alpha\nfuredea/beta\nfuredea/gamma"})
    assert result.returncode == 1
    assert marker.read_text() == "keep\n"
    assert "[summary] cloned=1 pulled=1 failed=1" in result.stdout
    assert not any("/gamma" in " ".join(row) for row in calls(remote, "git"))
    assert not any(row[:3] == ["repo", "clone", "furedea/gamma"] for row in calls(remote))


def test_direct_entry_point_ignores_project_and_user_module_injection(tmp_path: Path) -> None:
    (tmp_path / "json.py").write_text('raise RuntimeError("untrusted json module")\n')
    (tmp_path / "sitecustomize.py").write_text('raise RuntimeError("untrusted user site")\n')
    result = subprocess.run(
        [str(REPO_ROOT / "github/repo.py"), "create", "--help"],
        cwd=tmp_path,
        env=os.environ | {"PYTHONPATH": str(tmp_path)},
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert "Usage:" in result.stderr
    assert "untrusted" not in result.stdout + result.stderr
