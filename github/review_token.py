"""Issue, store, and register the review tokens behind `repo review-token` and `repo configure`."""

import getpass
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
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


def output(*arguments: str) -> str:
    """Read a command's stdout without interpreting its arguments as shell input."""
    return subprocess.check_output(arguments, text=True).rstrip("\n")


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


def requested_kinds(arguments: list[str]) -> list[str] | None:
    """Parse `rotate [kind]` into the kinds to rotate (all when none is named), or None when malformed."""
    if not arguments or arguments[0] != "rotate" or len(arguments) > 2:
        return None
    kinds = arguments[1:] or list(REVIEWERS)
    return None if any(kind not in REVIEWERS for kind in kinds) else kinds


def rotate(kinds: list[str]) -> int:
    """Rotate each named review token and return the worst status."""
    one_password = uses_one_password()
    return max(rotate_review_token(REVIEWERS[kind], one_password) for kind in kinds)
