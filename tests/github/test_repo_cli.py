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
    sentinel = owner / "gamma/sentinel"
    sentinel.write_text("keep\n")
    result = run_cli(SCRIPT, "sync", env={"GH_REPOSITORIES": "furedea/alpha\nfuredea/beta\nfuredea/gamma"})
    assert result.returncode == 1
    assert sentinel.read_text() == "keep\n"
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
