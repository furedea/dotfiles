#!/usr/bin/env -S python3 -IB
"""Run the personal GitHub workflow without shell-based data processing."""

import contextlib
import getpass
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VISIBILITIES = {"--public", "--private", "--internal"}
LOCAL_OPTIONS = {"--clone", "-c", "--source", "-s", "--push", "--remote", "-r"}
KEYCHAIN_SAFE_TOKEN = re.compile(r"[A-Za-z0-9._~+/=-]+")


@dataclass(frozen=True)
class Reviewer:
    """A review workflow's credential: how it is issued, where it is stored, and its Actions entry."""

    kind: str
    actions_entry: str
    one_password_title: str
    keychain_service: str
    setup_command: tuple[str, ...]
    instructions: str

    def issue(self) -> None:
        """Start issuing a new token; the user then pastes it."""
        if self.instructions:
            print(self.instructions, file=sys.stderr)
        if self.setup_command:
            subprocess.run(list(self.setup_command), check=True)


CLAUDE_REVIEWER = Reviewer(
    kind="claude",
    actions_entry="CLAUDE_CODE_OAUTH_TOKEN",
    one_password_title="Claude review token",
    keychain_service="claude-review-token",
    setup_command=("claude", "setup-token"),
    instructions="",
)
CODEX_REVIEWER = Reviewer(
    kind="codex",
    actions_entry="CODEX_REVIEW_TOKEN",
    one_password_title="Codex review token",
    keychain_service="codex-review-token",
    setup_command=(),
    instructions=(
        "Create a fine-grained token at https://github.com/settings/personal-access-tokens/new\n"
        "Resource owner: your account; Repository access: All repositories;\n"
        "Permissions: Pull requests read and write only; Expiration: one year."
    ),
)
REVIEWERS = {reviewer.kind: reviewer for reviewer in (CLAUDE_REVIEWER, CODEX_REVIEWER)}


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
        "review-token": "repo review-token rotate [claude|codex]",
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
        print("rotate issues a review token, stores it in 1Password (or the macOS Keychain) and", file=sys.stderr)
        print("registers it as an Actions secret on every owned, non-archived, non-fork repository:", file=sys.stderr)
        print(
            "claude runs `claude setup-token` (CLAUDE_CODE_OAUTH_TOKEN); codex asks for a fine-grained",
            file=sys.stderr,
        )
        print(
            "token that posts `@codex review` (CODEX_REVIEW_TOKEN). Without a kind, both are rotated.", file=sys.stderr
        )
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


def codeql_skip_reason(repository: str) -> str:
    """Name why default setup must not be applied, or return "" when it should be."""
    if output("gh", "api", f"repos/{repository}", "--jq", ".visibility") != "public":
        return "not a public repository"
    endpoint = f"repos/{repository}/code-scanning/default-setup"
    if output("gh", "api", endpoint, "--jq", ".state") == "configured":
        return "already configured"
    return ""


def enable_codeql_default_setup(repository: str) -> None:
    """Enable default setup on public repositories; a failure only warns.

    Policy: every repository uses default setup and no codeql.yml. Enabling it deliberately takes over from any
    advanced workflow, whose upload is then rejected; turning default setup off reverses that.
    """
    try:
        reason = codeql_skip_reason(repository)
        if reason:
            print(f"Skipped CodeQL default setup on {repository}: {reason}")
            return
        endpoint = f"repos/{repository}/code-scanning/default-setup"
        command = ["gh", "api", endpoint, "-X", "PATCH", "-f", "state=configured", "-f", "query_suite=default"]
        subprocess.run(command, stdout=subprocess.DEVNULL, check=True)
        print(f"Enabled CodeQL default setup on {repository}")
    except subprocess.CalledProcessError:
        print(f"warning: could not enable CodeQL default setup on {repository}", file=sys.stderr)


def enable_immutable_releases(repository: str) -> None:
    """Lock future releases' tags and assets (existing releases stay mutable); a failure only warns."""
    command = ["gh", "api", f"repos/{repository}/immutable-releases", "-X", "PUT"]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError:
        print(f"warning: could not enable immutable releases on {repository}", file=sys.stderr)
        return
    print(f"Enabled immutable releases on {repository}")


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
    for reviewer in REVIEWERS.values():
        register_stored_review_token(repository, reviewer)
    enable_immutable_releases(repository)
    enable_codeql_default_setup(repository)


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
    print("[summary] " + " ".join(f"{key}={count}" for key, count in counts.items()))
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


def stored_review_token(reviewer: Reviewer) -> str | None:
    """Read the token from the one backend that the environment selects."""
    if uses_one_password():
        return read_secret_output(
            ["op", "item", "get", reviewer.one_password_title, "--fields", "label=credential", "--reveal"]
        )
    return read_secret_output(
        ["security", "find-generic-password", "-a", reviewer.actions_entry, "-s", reviewer.keychain_service, "-w"]
    )


def store_in_one_password(reviewer: Reviewer, value: str) -> None:
    """Update the item in place, or create it, with the JSON item on stdin."""
    template = {
        "title": reviewer.one_password_title,
        "category": "API_CREDENTIAL",
        "fields": [{"id": "credential", "type": "CONCEALED", "label": "credential", "value": value}],
    }
    exists = subprocess.run(
        ["op", "item", "get", reviewer.one_password_title],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    verb = ["edit", reviewer.one_password_title] if exists.returncode == 0 else ["create"]
    subprocess.run(["op", "item", *verb], input=json.dumps(template), stdout=subprocess.DEVNULL, text=True, check=True)


def store_in_keychain(reviewer: Reviewer, value: str) -> None:
    """Update the Keychain item through `security -i`, so the token travels on stdin only."""
    if not KEYCHAIN_SAFE_TOKEN.fullmatch(value):
        raise ValueError("repo review-token: the token contains characters the Keychain command cannot carry safely")
    command = f"add-generic-password -U -a {reviewer.actions_entry} -s {reviewer.keychain_service} -w {value}\n"
    subprocess.run(["security", "-i"], input=command, stdout=subprocess.DEVNULL, text=True, check=True)


def store_review_token(reviewer: Reviewer, value: str, one_password: bool) -> str:
    """Store the token in the selected backend and name the one used."""
    if one_password:
        store_in_one_password(reviewer, value)
        return "1Password"
    store_in_keychain(reviewer, value)
    return "macOS Keychain"


def set_review_secret(repository: str, reviewer: Reviewer, value: str) -> None:
    """Register the token as the repository's Actions secret, passing it on stdin only."""
    subprocess.run(
        ["gh", "secret", "set", reviewer.actions_entry, "--repo", repository],
        input=value,
        stdout=subprocess.DEVNULL,
        text=True,
        check=True,
    )


def register_stored_review_token(repository: str, reviewer: Reviewer) -> None:
    """Register the stored token on one repository, or warn when none has been stored."""
    value = stored_review_token(reviewer)
    if value is None:
        print(
            f"warning: no stored {reviewer.kind} review token; "
            f"run `repo review-token rotate {reviewer.kind}` to register {reviewer.actions_entry}",
            file=sys.stderr,
        )
        return
    set_review_secret(repository, reviewer, value)
    print(f"Registered {reviewer.actions_entry} on {repository}")


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


def read_pasted_token(reviewer: Reviewer) -> str:
    """Read the token without echoing it when interactive, or one line of stdin otherwise."""
    if sys.stdin.isatty():
        value = getpass.getpass(f"Paste the {reviewer.kind} review token: ")
    else:
        value = sys.stdin.readline()
    value = value.strip()
    if not value:
        raise ValueError("repo review-token: no token was provided")
    return value


def rotate_review_token(reviewer: Reviewer, one_password: bool) -> int:
    """Issue a new token, store it, and register it on every target repository."""
    reviewer.issue()
    value = read_pasted_token(reviewer)
    print(f"Stored the {reviewer.kind} review token in {store_review_token(reviewer, value, one_password)}")
    counts = {"registered": 0, "failed": 0}
    for repository in review_token_targets():
        try:
            set_review_secret(repository, reviewer, value)
            counts["registered"] += 1
        except subprocess.CalledProcessError:
            print(f"Failed to register {reviewer.actions_entry} on {repository}", file=sys.stderr)
            counts["failed"] += 1
    print(f"[summary {reviewer.kind}] " + " ".join(f"{key}={count}" for key, count in counts.items()))
    return int(counts["failed"] != 0)


def review_token_command(arguments: list[str]) -> int:
    """Dispatch the review-token subcommands; without a kind, rotate every review token."""
    if not arguments or arguments[0] != "rotate" or len(arguments) > 2:
        return usage("review-token")
    kinds = arguments[1:] or list(REVIEWERS)
    if any(kind not in REVIEWERS for kind in kinds):
        return usage("review-token")
    one_password = uses_one_password()
    return max(rotate_review_token(REVIEWERS[kind], one_password) for kind in kinds)


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
