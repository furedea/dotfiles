"""Run the personal GitHub workflow without shell-based data processing."""

import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
VISIBILITIES = {"--public", "--private", "--internal"}
LOCAL_OPTIONS = {"--clone", "-c", "--source", "-s", "--push", "--remote", "-r"}


def output(*arguments: str) -> str:
    """Read a command's stdout without interpreting its arguments as shell input."""
    return subprocess.check_output(arguments, text=True).rstrip("\n")


def repository_name(name: str) -> str:
    """Resolve a short repository name against the authenticated owner."""
    if "/" in name:
        return name
    return f"{output('gh', 'api', 'user', '--jq', '.login')}/{name}"


def usage(command: str = "") -> int:
    """Describe the selected command on stderr, preserving the existing CLI status."""
    descriptions = {
        "create": "repo create <name-or-owner/name> <visibility> [options]",
        "configure": "repo configure <name-or-owner/name>",
        "sync": "repo sync [--dry-run]",
    }
    print(f"Usage: {descriptions.get(command, 'repo <create|configure|sync> [arguments]')}", file=sys.stderr)
    print("Options: --help, -h", file=sys.stderr)
    if command == "create":
        print("Visibility: set exactly one of --public, --private, or --internal.", file=sys.stderr)
        print("Supports --template/-p, --description/-d, --homepage, --add-readme, --gitignore/-g,", file=sys.stderr)
        print("--license/-l, --team/-t, --include-all-branches, --disable-issues and --disable-wiki.", file=sys.stderr)
        print("Local --clone, --source, --push and --remote options are not supported.", file=sys.stderr)
        print(
            "Other compatible gh repo create options are forwarded. The clone destination is printed to stdout.",
            file=sys.stderr,
        )
        print("Example: repo create agent-harness --private --template furedea/template-rust", file=sys.stderr)
    return 1


def create_options(arguments: list[str]) -> bool:
    """Validate the local clone contract and report whether a template was selected."""
    for argument in arguments:
        if argument.split("=", 1)[0] in LOCAL_OPTIONS:
            raise ValueError(
                f"repo create: {argument} is not supported; repo create controls the local clone destination"
            )
    if sum(argument in VISIBILITIES for argument in arguments) != 1:
        raise ValueError("repo create: exactly one of --public, --private, or --internal is required")
    return any(argument.split("=", 1)[0] in {"--template", "-p"} for argument in arguments)


def wait_for_default_branch(repository: str) -> None:
    """Wait until GitHub exposes the template's actual default branch reference."""
    for _ in range(30):
        try:
            with open(os.devnull, "w") as errors:
                branch = subprocess.check_output(
                    ["gh", "api", f"repos/{repository}", "--jq", ".default_branch // empty"],
                    text=True,
                    stderr=errors,
                ).strip()
                if branch:
                    reference = subprocess.check_output(
                        ["gh", "api", f"repos/{repository}/git/ref/heads/{branch}", "--jq", ".ref // empty"],
                        text=True,
                        stderr=errors,
                    ).strip()
                    if reference == f"refs/heads/{branch}":
                        return
        except subprocess.CalledProcessError:
            pass
        subprocess.run(["sleep", "2"], check=True)
    raise ValueError(f"repo create: remote default branch is not ready: {repository}")


def apply_template(destination: Path, name: str) -> None:
    """Rename template packages while retaining unrelated manifest content."""
    for filename in ("pyproject.toml", "Cargo.toml"):
        path = destination / filename
        if path.is_file():
            contents = path.read_text()
            path.write_text(
                re.sub(
                    r'^name = "template-[a-z]*"', lambda _: f'name = "{name}"', contents, count=1, flags=re.MULTILINE
                )
            )
    package = destination / "package.json"
    if package.is_file():
        data = json.loads(package.read_text())
        data["name"] = name
        package.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def configure(repository: str) -> None:
    """Apply the source-controlled settings and upsert the named ruleset."""
    subprocess.run(
        ["gh", "api", f"repos/{repository}", "-X", "PATCH", "--input", str(ROOT / "repo_settings.json")],
        stdout=subprocess.DEVNULL,
        check=True,
    )
    print(f"Applied repo settings to {repository}")
    subprocess.run(
        ["gh", "api", f"repos/{repository}/vulnerability-alerts", "-X", "PUT"], stdout=subprocess.DEVNULL, check=True
    )
    print(f"Enabled vulnerability alerts and dependency graph on {repository}")
    ruleset = ROOT / "ruleset.json"
    name = json.loads(ruleset.read_text())["name"]
    identifier = output(
        "gh", "api", f"repos/{repository}/rulesets", "--jq", f".[] | select(.name == {json.dumps(name)}) | .id"
    )
    endpoint = f"repos/{repository}/rulesets" + (f"/{identifier}" if identifier else "")
    subprocess.run(
        ["gh", "api", endpoint, "-X", "PUT" if identifier else "POST", "--input", str(ruleset)],
        stdout=subprocess.DEVNULL,
        check=True,
    )
    print(f"Updated ruleset {identifier} on {repository}" if identifier else f"Created ruleset on {repository}")


def create(arguments: list[str]) -> int:
    """Create and configure a repository, printing only its clone destination."""
    if not arguments or any(argument in {"--help", "-h"} for argument in arguments):
        return usage("create")
    name, *options = arguments
    has_template = create_options(options)
    repository = repository_name(name)
    destination = Path(output("ghq", "root")) / "github.com" / repository
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"repo create: local destination already exists: {destination}")
    print(f"→ creating GitHub repo: {repository}", file=sys.stderr)
    subprocess.run(["gh", "repo", "create", name, *options], stdout=sys.stderr, check=True)
    if has_template:
        print(f"→ waiting for template repository to become cloneable: {repository}", file=sys.stderr)
        wait_for_default_branch(repository)
    print(f"→ cloning into {destination}", file=sys.stderr)
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gh", "repo", "clone", repository, str(destination)], stdout=sys.stderr, check=True)
    apply_template(destination, name.rsplit("/", 1)[-1])
    with contextlib.redirect_stdout(sys.stderr):
        configure(repository)
    if (destination / "lefthook.yml").is_file() and shutil.which("lefthook"):
        subprocess.run(["lefthook", "install"], cwd=destination, stdout=sys.stderr, check=True)
    print(destination)
    return 0


def sync_repository(repository: str, target: Path, dry_run: bool) -> str:
    """Clone or fast-forward one repository without replacing an unrelated path."""
    if not target.exists():
        print(f"[clone] {repository} -> {target}", flush=True)
        if not dry_run:
            subprocess.run(["gh", "repo", "clone", repository, str(target)], check=True)
        return "cloned"
    if not (target / ".git").exists():
        raise ValueError(f"Not a Git repository: {target}")
    print(f"[pull] {target}", flush=True)
    if not dry_run:
        subprocess.run(["git", "-C", str(target), "pull", "--ff-only"], check=True)
    return "pulled"


def sync(arguments: list[str]) -> int:
    """Synchronize owned repositories and report independent failures."""
    if arguments not in ([], ["--dry-run"]):
        return usage("sync")
    dry_run = bool(arguments)
    owner = output("gh", "api", "user", "--jq", ".login")
    owner_directory = Path(output("ghq", "root")) / "github.com" / owner
    repositories = output(
        "gh", "repo", "list", owner, "--limit", "10000", "--json", "nameWithOwner", "--jq", ".[].nameWithOwner"
    )
    if not dry_run:
        owner_directory.mkdir(parents=True, exist_ok=True)
    counts = {"cloned": 0, "pulled": 0, "failed": 0}
    for repository in filter(None, repositories.splitlines()):
        try:
            operation = sync_repository(repository, owner_directory / repository.split("/", 1)[-1], dry_run)
            counts[operation] += 1
        except (subprocess.CalledProcessError, OSError, ValueError) as error:
            print(error, file=sys.stderr)
            counts["failed"] += 1
    print("[summary] " + " ".join(f"{key}={value}" for key, value in counts.items()))
    return int(counts["failed"] != 0)


def main(arguments: list[str]) -> int:
    """Dispatch the public repository commands."""
    if not arguments:
        return usage()
    command, *remaining = arguments
    try:
        if command == "create":
            return create(remaining)
        if command == "sync":
            return sync(remaining)
        if command == "configure":
            if len(remaining) != 1 or remaining[0].startswith("-"):
                return usage(command)
            configure(repository_name(remaining[0]))
            return 0
        return usage()
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode > 0 else 1
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
