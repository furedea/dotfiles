#!/usr/bin/env -S python3 -IB
"""Remove task worktrees and local branches whose pull requests were merged.

A branch goes only when a merged pull request's head is exactly its tip and its worktree is
clean, so a squash merge counts as merged while later or uncommitted work is kept. The primary
checkout, the worktree the caller runs in, and the default branch are never removed; after a
removal the default branch fast-forwards to the merges unless that would disturb work. The sweep
covers the caller's repository and every repository with a Herdr task worktree, so lanes merged
elsewhere go wherever the next session starts.

Usage: cleanup_worktrees.py [--dry-run]
       cleanup_worktrees.py session-start  as a hook, reading the payload's cwd
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys


PROTECTED_BRANCHES = frozenset({"main", "master"})
MERGED_PULL_REQUEST_LIMIT = "200"
TIMEOUT_SECONDS = 30
HERDR_WORKTREES = Path(".herdr/worktrees")
"""Herdr's default worktrees.directory, holding <repo>/<branch-slug> checkouts."""


@dataclass(frozen=True, slots=True)
class Worktree:
    path: Path
    branch: str


def main(arguments: list[str]) -> int:
    if arguments == ["session-start"]:
        try:
            payload = json.load(sys.stdin)
            sweep(Path(payload["cwd"]), dry_run=False)
        except ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError:
            pass
        return 0
    if arguments not in ([], ["--dry-run"]):
        print(__doc__, file=sys.stderr)
        return 1
    try:
        for line in sweep(Path.cwd(), dry_run=bool(arguments)):
            print(line)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"cleanup failed: {error}", file=sys.stderr)
        return 1
    return 0


def sweep(cwd: Path, *, dry_run: bool) -> list[str]:
    """Clean the caller's repository and every repository with a Herdr task worktree."""
    current = toplevel(cwd)
    lanes = sorted(path for path in (Path.home() / HERDR_WORKTREES).glob("*/*") if path.is_dir())
    primaries = {primary for primary in map(primary_checkout, [cwd, *lanes]) if primary}
    report = []
    for primary in sorted(primaries):
        try:
            report += cleanup(primary, current, dry_run=dry_run)
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            report.append(f"skip {primary}: {error}")
    return report


def toplevel(path: Path) -> Path | None:
    try:
        return Path(run("git", "rev-parse", "--show-toplevel", cwd=path)).resolve()
    except OSError, subprocess.SubprocessError:
        return None


def primary_checkout(path: Path) -> Path | None:
    try:
        common = Path(run("git", "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=path))
    except OSError, subprocess.SubprocessError:
        return None
    return common.parent.resolve()


def cleanup(primary: Path, current: Path | None, *, dry_run: bool) -> list[str]:
    """Remove what is merged in one repository and return one line per removal."""
    merged = merged_heads(primary)
    worktrees = linked_worktrees(primary)
    checked_out = {worktree.branch for worktree in worktrees} | {current_branch(primary)}
    workspaces = herdr_workspaces(primary)
    report = []
    for worktree in worktrees:
        if worktree.path in {primary, current} or not is_merged(primary, worktree.branch, merged):
            continue
        if run("git", "status", "--porcelain", cwd=worktree.path):
            continue
        report.append(f"remove worktree {worktree.path} and branch {worktree.branch}")
        if not dry_run:
            remove_worktree(primary, worktree, workspaces.get(worktree.path))
            run("git", "branch", "-D", worktree.branch, cwd=primary)
    for branch in local_branches(primary) - checked_out:
        if not is_merged(primary, branch, merged):
            continue
        report.append(f"remove branch {branch}")
        if not dry_run:
            run("git", "branch", "-D", branch, cwd=primary)
    if report:
        report += fast_forward_default_branch(primary, dry_run=dry_run)
    return report


def fast_forward_default_branch(primary: Path, *, dry_run: bool) -> list[str]:
    """Bring the default branch up to the merges just cleaned up, without touching other work.

    A checked-out default branch is pulled only when its tree is clean; otherwise only its ref
    moves, through a fetch that refuses anything but a fast-forward.
    """
    branch = next((name for name in sorted(PROTECTED_BRANCHES) if has_branch(primary, name)), "")
    if not branch:
        return []
    checked_out = current_branch(primary) == branch
    if checked_out and run("git", "status", "--porcelain", cwd=primary):
        return []
    pull = ("git", "pull", "--quiet", "--ff-only")
    fetch = ("git", "fetch", "--quiet", "origin", f"{branch}:{branch}")
    if not dry_run:
        try:
            run(*(pull if checked_out else fetch), cwd=primary)
        except subprocess.CalledProcessError:
            return []
    return [f"fast-forward {branch}"]


def has_branch(primary: Path, branch: str) -> bool:
    return bool(run("git", "for-each-ref", "--format=%(refname)", f"refs/heads/{branch}", cwd=primary))


def is_merged(primary: Path, branch: str, merged: dict[str, set[str]]) -> bool:
    if not branch or branch in PROTECTED_BRANCHES:
        return False
    return run("git", "rev-parse", f"refs/heads/{branch}", cwd=primary) in merged.get(branch, set())


def merged_heads(primary: Path) -> dict[str, set[str]]:
    """Map each branch to the head commits of its merged pull requests."""
    output = run(
        "gh",
        "pr",
        "list",
        "--state",
        "merged",
        "--limit",
        MERGED_PULL_REQUEST_LIMIT,
        "--json",
        "headRefName,headRefOid",
        cwd=primary,
    )
    heads: dict[str, set[str]] = {}
    for pull_request in json.loads(output or "[]"):
        heads.setdefault(pull_request["headRefName"], set()).add(pull_request["headRefOid"])
    return heads


def linked_worktrees(primary: Path) -> list[Worktree]:
    worktrees = []
    for block in run("git", "worktree", "list", "--porcelain", cwd=primary).split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        branch = fields.get("branch", "").removeprefix("refs/heads/")
        if "worktree" in fields and branch:
            worktrees.append(Worktree(Path(fields["worktree"]).resolve(), branch))
    return worktrees


def local_branches(primary: Path) -> set[str]:
    return set(run("git", "for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=primary).splitlines())


def current_branch(primary: Path) -> str:
    return run("git", "branch", "--show-current", cwd=primary)


def herdr_workspaces(primary: Path) -> dict[Path, str]:
    """Map open Herdr worktree workspaces by path; without Herdr there are none to close."""
    try:
        output = run("herdr", "worktree", "list", "--cwd", str(primary), cwd=primary)
        worktrees = json.loads(output)["result"]["worktrees"]
    except OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError:
        return {}
    return {
        Path(item["path"]).resolve(): item["open_workspace_id"]
        for item in worktrees
        if isinstance(item, dict) and item.get("path") and item.get("open_workspace_id")
    }


def remove_worktree(primary: Path, worktree: Worktree, workspace: str | None) -> None:
    """Close the Herdr workspace with the checkout when one is open; Git refuses a dirty tree either way."""
    if workspace:
        run("herdr", "worktree", "remove", "--workspace", workspace, cwd=primary)
    else:
        run("git", "worktree", "remove", str(worktree.path), cwd=primary)


def run(*command: str, cwd: Path) -> str:
    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, check=True, timeout=TIMEOUT_SECONDS, env=os.environ
    ).stdout.strip()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
