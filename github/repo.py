#!/usr/bin/env -S python3 -IB
"""Run the personal GitHub workflow without shell-based data processing."""

import contextlib
import getpass
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
VISIBILITIES = {"--public", "--private", "--internal"}
LOCAL_OPTIONS = {"--clone", "-c", "--source", "-s", "--push", "--remote", "-r"}
ACTIONS_ENTRY_NAME = "CLAUDE_CODE_OAUTH_TOKEN"
ONE_PASSWORD_TITLE = "Claude review token"
KEYCHAIN_SERVICE = "claude-review-token"
KEYCHAIN_ACCOUNT = ACTIONS_ENTRY_NAME
KEYCHAIN_SAFE_TOKEN = re.compile(r"[A-Za-z0-9._~+/=-]+")


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
        "review-token": "repo review-token rotate",
    }
    print(f"Usage: {descriptions.get(command, 'repo <command> [arguments]')}", file=sys.stderr)
    if not command:
        print("Commands: create, configure, sync, review-token", file=sys.stderr)
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
    if command == "review-token":
        print("rotate issues a Claude review token with `claude setup-token`, stores it in", file=sys.stderr)
        print("1Password (or the macOS Keychain) and registers it as the Actions secret", file=sys.stderr)
        print(f"{ACTIONS_ENTRY_NAME} on every owned, non-archived, non-fork repository.", file=sys.stderr)
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
        if default_branch_ready(repository):
            return
        subprocess.run(["sleep", "2"], check=True)
    raise ValueError(f"repo create: remote default branch is not ready: {repository}")


def default_branch_ready(repository: str) -> bool:
    """Report whether GitHub resolves the default branch name to its reference yet."""
    try:
        branch = subprocess.check_output(
            ["gh", "api", f"repos/{repository}", "--jq", ".default_branch // empty"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not branch:
            return False
        reference = subprocess.check_output(
            ["gh", "api", f"repos/{repository}/git/ref/heads/{branch}", "--jq", ".ref // empty"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return False
    return reference == f"refs/heads/{branch}"


def apply_template(destination: Path, repository: str) -> None:
    """Rename template packages and the Go module while retaining unrelated manifest content."""
    owner, name = repository.split("/", 1)
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
    go_module = destination / "go.mod"
    if go_module.is_file():
        go_module.write_text(
            re.sub(
                r"^module .*$",
                lambda _: f"module github.com/{owner}/{name}",
                go_module.read_text(),
                count=1,
                flags=re.MULTILINE,
            )
        )


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
    register_stored_review_token(repository)


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
    apply_template(destination, repository)
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


def uses_one_password() -> bool:
    """Choose the backend: 1Password when `op` is installed, Keychain when it is not.

    An installed but signed-out `op` is an error, never a reason to switch backends.
    """
    if shutil.which("op") is None:
        return False
    probe = subprocess.run(["op", "whoami"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if probe.returncode != 0:
        raise ValueError("repo review-token: 1Password is not signed in; run `op signin` and retry")
    return True


def read_secret_output(arguments: list[str]) -> str | None:
    """Return a command's trimmed stdout, or None when the command is missing or fails."""
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    except OSError:
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def stored_review_token() -> str | None:
    """Read the token from the one backend that the environment selects."""
    if uses_one_password():
        return read_secret_output(
            ["op", "item", "get", ONE_PASSWORD_TITLE, "--fields", "label=credential", "--reveal"]
        )
    return read_secret_output(
        ["security", "find-generic-password", "-a", KEYCHAIN_ACCOUNT, "-s", KEYCHAIN_SERVICE, "-w"]
    )


def existing_one_password_item_ids() -> list[str]:
    """Return the ids of every 1Password item with the token's title, including duplicates."""
    listing = read_secret_output(["op", "item", "list", "--format", "json"])
    items = json.loads(listing) if listing else []
    return [item["id"] for item in items if item["title"] == ONE_PASSWORD_TITLE]


def store_in_one_password(token: str) -> None:
    """Create the new item from a JSON template on stdin, then remove the previous ones by id."""
    previous_ids = existing_one_password_item_ids()
    template = {
        "title": ONE_PASSWORD_TITLE,
        "category": "API_CREDENTIAL",
        "fields": [{"id": "credential", "type": "CONCEALED", "label": "credential", "value": token}],
    }
    created = subprocess.run(
        ["op", "item", "create", "--format", "json"],
        input=json.dumps(template),
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    try:
        for previous_id in previous_ids:
            subprocess.run(["op", "item", "delete", previous_id], stdout=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError as error:
        subprocess.run(
            ["op", "item", "delete", json.loads(created.stdout)["id"]], stdout=subprocess.DEVNULL, check=False
        )
        raise ValueError(
            "repo review-token: could not remove the previous 1Password item; nothing was changed"
        ) from error


def store_in_keychain(token: str) -> None:
    """Update the Keychain item through `security -i`, so the token travels on stdin only."""
    if not KEYCHAIN_SAFE_TOKEN.fullmatch(token):
        raise ValueError("repo review-token: the token contains characters the Keychain command cannot carry safely")
    command = f"add-generic-password -U -a {KEYCHAIN_ACCOUNT} -s {KEYCHAIN_SERVICE} -w {token}\n"
    subprocess.run(["security", "-i"], input=command, stdout=subprocess.DEVNULL, text=True, check=True)


def store_review_token(token: str, one_password: bool) -> str:
    """Store the token in the selected backend and name the one used."""
    if one_password:
        store_in_one_password(token)
        return "1Password"
    store_in_keychain(token)
    return "macOS Keychain"


def set_review_secret(repository: str, token: str) -> None:
    """Register the token as the repository's Actions secret, passing it on stdin only."""
    subprocess.run(
        ["gh", "secret", "set", ACTIONS_ENTRY_NAME, "--repo", repository],
        input=token,
        stdout=subprocess.DEVNULL,
        text=True,
        check=True,
    )


def register_stored_review_token(repository: str) -> None:
    """Register the stored token on one repository, or warn when none has been stored."""
    token = stored_review_token()
    if token is None:
        print(
            f"warning: no stored review token; run `repo review-token rotate` to register {ACTIONS_ENTRY_NAME}",
            file=sys.stderr,
        )
        return
    set_review_secret(repository, token)
    print(f"Registered {ACTIONS_ENTRY_NAME} on {repository}")


def review_token_targets() -> list[str]:
    """List the owner's active, non-fork repositories that are not excluded."""
    owner = output("gh", "api", "user", "--jq", ".login")
    excluded = set(json.loads((ROOT / "review_exclusions.json").read_text()))
    names = output(
        "gh",
        "repo",
        "list",
        owner,
        "--limit",
        "10000",
        "--no-archived",
        "--source",
        "--json",
        "name",
        "--jq",
        ".[].name",
    )
    return [f"{owner}/{name}" for name in names.splitlines() if name and name not in excluded]


def read_pasted_token() -> str:
    """Read the token without echoing it when interactive, or from stdin otherwise."""
    if sys.stdin.isatty():
        token = getpass.getpass("Paste the token from `claude setup-token`: ")
    else:
        token = sys.stdin.readline()
    token = token.strip()
    if not token:
        raise ValueError("repo review-token: no token was provided")
    return token


def rotate_review_token() -> int:
    """Issue a new token, store it, and register it on every target repository."""
    one_password = uses_one_password()
    subprocess.run(["claude", "setup-token"], check=True)
    token = read_pasted_token()
    print(f"Stored the review token in {store_review_token(token, one_password)}")
    counts = {"registered": 0, "failed": 0}
    for repository in review_token_targets():
        try:
            set_review_secret(repository, token)
            counts["registered"] += 1
        except subprocess.CalledProcessError:
            print(f"Failed to register {ACTIONS_ENTRY_NAME} on {repository}", file=sys.stderr)
            counts["failed"] += 1
    print("[summary] " + " ".join(f"{key}={value}" for key, value in counts.items()))
    return int(counts["failed"] != 0)


def review_token_command(arguments: list[str]) -> int:
    """Dispatch the review-token subcommands."""
    if arguments != ["rotate"]:
        return usage("review-token")
    return rotate_review_token()


def configure_command(arguments: list[str]) -> int:
    """Configure exactly one named repository."""
    if len(arguments) != 1 or arguments[0].startswith("-"):
        return usage("configure")
    configure(repository_name(arguments[0]))
    return 0


COMMANDS = {"create": create, "sync": sync, "configure": configure_command, "review-token": review_token_command}


def main(arguments: list[str]) -> int:
    """Dispatch the public repository commands."""
    if not arguments:
        return usage()
    command, *remaining = arguments
    handler = COMMANDS.get(command)
    if handler is None:
        return usage()
    try:
        return handler(remaining)
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode > 0 else 1
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
