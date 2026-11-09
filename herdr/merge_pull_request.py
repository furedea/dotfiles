#!/usr/bin/env -S python3 -IB
"""Approve and confirm an immediate squash merge without hiding command failures or unsafe cleanup."""

import json
import os
import subprocess
import sys
import termios
import tty
from dataclasses import dataclass


def read_key() -> str:
    """Read one key press, in raw mode when stdin is a terminal.

    Returns:
        The character read, or an empty string at end of input.
    """
    if not sys.stdin.isatty():
        return sys.stdin.read(1)
    descriptor = sys.stdin.fileno()
    settings = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, settings)


def wait_for_close() -> None:
    """Block until Enter, Esc, Ctrl+C or end of input so the pane output stays readable."""
    print("\nPress Enter or Esc to close...", end="", flush=True)
    while read_key() not in {"", "\n", "\r", "\x1b", "\x03"}:
        pass
    print()


def confirm(accepted: set[str]) -> bool:
    """Ask for one key press and report whether it is one of the accepted keys.

    Args:
        accepted: Keys that confirm the action.

    Returns:
        True when an accepted key was pressed; any other key cancels.
    """
    answer = read_key()
    if answer in accepted:
        return True
    print("\nCancelled.")
    if answer not in {"", "\x1b", "\x03"}:
        wait_for_close()
    return False


def checked_out(branch: str, worktrees: str) -> bool:
    """Report whether any worktree in `git worktree list --porcelain` output has the branch checked out."""
    return f"branch refs/heads/{branch}" in worktrees.splitlines()


def capture(arguments: list[str]) -> str:
    """Run a command and return its stripped standard output.

    Raises:
        subprocess.CalledProcessError: The command exited with a non-zero status.
    """
    return subprocess.check_output(arguments, text=True).strip()


@dataclass(frozen=True)
class PullRequest:
    """Snapshot of the pull request fields needed to decide whether and how to merge."""

    number: int
    title: str
    base: str
    head: str
    head_commit: str
    author: str
    approved_commits: frozenset[str]
    checks: list[dict]

    @classmethod
    def parse(cls, raw: str, viewer: str) -> PullRequest:
        """Build a snapshot from `gh pr view --json` output.

        Args:
            raw: JSON text produced by `gh pr view`.
            viewer: Login of the current user, whose approvals are collected.

        Returns:
            The parsed pull request.
        """
        data = json.loads(raw)
        approved: set[str] = {
            review["commit"]["oid"]
            for review in data["latestReviews"]
            if review["state"] == "APPROVED" and review["author"]["login"] == viewer and review.get("commit")
        }
        return cls(
            number=data["number"],
            title=data["title"],
            base=data["baseRefName"],
            head=data["headRefName"],
            head_commit=data["headRefOid"],
            author=data["author"]["login"],
            approved_commits=frozenset(approved),
            checks=data["statusCheckRollup"] or [],
        )

    def checks_state(self) -> str:
        """Summarize all checks as "none", "failed", "pending" or "passed", with failure taking precedence."""
        if not self.checks:
            return "none"
        states = {check_state(check) for check in self.checks}
        return "failed" if "failed" in states else "pending" if "pending" in states else "passed"

    def approved_by(self, commit: str) -> bool:
        """Report whether the viewer approved exactly this commit."""
        return commit in self.approved_commits


def check_state(check: dict) -> str:
    """Classify one status check from `statusCheckRollup` as "pending", "passed" or "failed"."""
    outcome = check.get("conclusion") or check.get("state") or ""
    if check.get("status", "COMPLETED") != "COMPLETED" or outcome in {"", "PENDING", "EXPECTED"}:
        return "pending"
    return "passed" if outcome in {"SUCCESS", "NEUTRAL", "SKIPPED"} else "failed"


def refusal(pull_request: PullRequest, commit: str) -> str:
    """Explain why the merge must not proceed.

    Returns:
        The reason, or an empty string when the local HEAD matches the pull request head and all checks passed.
    """
    if commit != pull_request.head_commit:
        return "local HEAD does not match the pull request head."
    if pull_request.checks_state() != "passed":
        return "required checks have not all succeeded."
    return ""


def merge(repository: str) -> int:
    """Show the pull request of the repository's current branch and merge it after confirmation.

    Args:
        repository: Directory inside the repository whose current branch has the pull request.

    Returns:
        The exit status: 0 on success or cancellation, non-zero on refusal or command failure.
    """
    git = os.environ.get("GIT_BIN", "git")
    gh = os.environ.get("GH_BIN", "gh")
    root = capture([git, "-C", repository, "rev-parse", "--show-toplevel"])
    os.chdir(root)
    if capture([git, "-C", root, "status", "--porcelain=v1"]):
        print("Cannot merge: working tree has uncommitted changes.")
        return 1
    fields = "number,title,baseRefName,headRefName,headRefOid,author,latestReviews,statusCheckRollup"
    raw = capture([gh, "pr", "view", "--json", fields])
    viewer = capture([gh, "api", "user", "--jq", ".login"])
    pull_request = PullRequest.parse(raw, viewer)
    commit = capture([git, "-C", root, "rev-parse", "HEAD"])
    worktrees = capture([git, "-C", root, "worktree", "list", "--porcelain"])
    arguments = [gh, "pr", "merge", "--squash"]
    base = pull_request.base
    if checked_out(base, worktrees):
        cleanup = f"keep this worktree and local branch; {base} is checked out elsewhere."
    else:
        arguments.append("--delete-branch")
        cleanup = f"delete the merged branch and switch to {base}."
    arguments += ["--match-head-commit", commit]
    own = pull_request.author == viewer
    approval = "approved by you" if pull_request.approved_by(commit) else "not yet approved"
    print(f"PR #{pull_request.number}: {pull_request.title}\n{pull_request.head} -> {base}\n")
    print(f"Author: {pull_request.author}\nChecks: {pull_request.checks_state()}\nApproval: {approval}")
    print(f"\nLocal cleanup: {cleanup}\n")
    reason = refusal(pull_request, commit)
    if reason:
        print(f"Cannot merge: {reason}")
        return 1
    if own:
        return merge_own(arguments)
    approve = [] if pull_request.approved_by(commit) else [gh, "pr", "review", str(pull_request.number), "--approve"]
    return approve_and_merge(approve, arguments)


def approve_and_merge(approve: list[str], arguments: list[str]) -> int:
    """Confirm, then approve (when needed) and squash-merge another author's pull request.

    Args:
        approve: The `gh pr review --approve` command, or an empty list when already approved.
        arguments: The `gh pr merge` command.

    Returns:
        The exit status of the first failing command, or of the merge.
    """
    print("Enter / Ctrl+M  Approve and squash-merge now\nEsc             Cancel", flush=True)
    if not confirm({"\n", "\r"}):
        return 0
    print(flush=True)
    if approve:
        status = subprocess.run(approve, check=False).returncode
        if status:
            return status
    return subprocess.run(arguments, check=False).returncode


def merge_own(arguments: list[str]) -> int:
    """Merge the user's own pull request with the admin bypass, only after an explicit "A" key press.

    Args:
        arguments: The `gh pr merge` command without `--admin`.

    Returns:
        0 when cancelled, otherwise the exit status of the merge.
    """
    print("You authored this PR and cannot approve it; merging needs the admin bypass.")
    print("Enter does not bypass.\n")
    print("A               Merge with admin bypass\nEsc             Cancel", flush=True)
    if not confirm({"A"}):
        return 0
    print(flush=True)
    return subprocess.run([*arguments, "--admin"], check=False).returncode


def main(arguments: list[str]) -> int:
    """Run the merge for one repository directory and keep the pane open on failure.

    Args:
        arguments: Exactly one repository directory.

    Returns:
        0 on success or cancellation, otherwise the failing status.
    """
    if len(arguments) != 1 or arguments[0] in {"-h", "--help"}:
        print("Usage: merge_pull_request.py <REPOSITORY_DIRECTORY>", file=sys.stderr)
        return 1
    try:
        try:
            status = merge(arguments[0])
        except subprocess.CalledProcessError as error:
            status = error.returncode
        except (OSError, ValueError) as error:
            print(str(error), file=sys.stderr)
            status = 1
        if status:
            wait_for_close()
        return status
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
