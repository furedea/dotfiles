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


sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import herdr_ownership
import session_store


PROTECTED_BRANCHES = frozenset({"main", "master"})
MERGED_PULL_REQUEST_LIMIT = "200"
TIMEOUT_SECONDS = 30
HERDR_WORKTREES = Path(".herdr/worktrees")
"""Herdr's default worktrees.directory, holding <repo>/<branch-slug> checkouts."""


@dataclass(frozen=True, slots=True)
class Worktree:
    path: Path
    branch: str
    admin_dir: Path | None


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
    primaries = {primary for path in [current, *lanes] if path and (primary := primary_checkout(path))}
    report = []
    for primary in sorted(primaries):
        try:
            report += cleanup(primary, current, dry_run=dry_run)
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            report.append(f"skip {primary}: {error}")
    return report


def toplevel(path: Path) -> Path | None:
    if not path.is_dir():
        return None
    roots = [root for root in (path.resolve(), *path.resolve().parents) if (root / ".git").exists()]
    for root in reversed(roots):
        primary = primary_checkout(root)
        if primary:
            known = {worktree.path for worktree in linked_worktrees(primary)}
            return next((ancestor for ancestor in roots if ancestor in known), None)
    return None


def primary_checkout(path: Path) -> Path | None:
    root = (
        next((root for root in (path.resolve(), *path.resolve().parents) if (root / ".git").exists()), None)
        if path.is_dir()
        else None
    )
    if root is None:
        return None
    if real_primary(root):
        writable = sandbox_writable_paths()
        return root if writable is None or not any(root.is_relative_to(path) for path in writable) else None
    return lane_primary(root)


def lane_primary(root: Path) -> Path | None:
    admin = git_file_target(root)
    if admin is None or admin.parent.name != "worktrees" or admin.parent.parent.name != ".git":
        return None
    primary = admin.parent.parent.parent
    writable = sandbox_writable_paths()
    if not real_primary(primary) or writable is None or any(primary.is_relative_to(path) for path in writable):
        return None
    try:
        if (
            Path((admin / "gitdir").read_text().strip()).resolve() != root / ".git"
            or (admin / (admin / "commondir").read_text().strip()).resolve() != primary / ".git"
        ):
            return None
        return (
            primary
            if any(worktree.path == root and worktree.admin_dir == admin for worktree in linked_worktrees(primary))
            else None
        )
    except OSError, subprocess.SubprocessError:
        pass
    return None


def real_primary(path: Path) -> bool:
    return (
        (path / ".git").is_dir()
        and not (path / ".git").is_symlink()
        and not path.is_relative_to((Path.home() / HERDR_WORKTREES).resolve())
    )


def sandbox_writable_paths() -> set[Path] | None:
    """Read rendered home policy before trusting any primary inferred from a lane."""
    home = Path.home().resolve()
    try:
        entries = json.loads((home / ".claude/settings.json").read_text())["sandbox"]["filesystem"]["allowWrite"]
        if not isinstance(entries, list) or any(not isinstance(entry, str) for entry in entries):
            return None
        paths = {
            home / entry.removeprefix("~").lstrip("/") if entry.startswith("~") else home / entry for entry in entries
        }
        paths.update(
            {
                Path("/tmp"),
                Path("/private/tmp"),
                Path("/tmp/claude"),
                Path("/private/tmp/claude"),
                home / HERDR_WORKTREES,
            }
        )
        if temporary := os.environ.get("TMPDIR"):
            paths.add(Path(temporary))
        return paths | {path.resolve() for path in paths}
    except OSError, ValueError, KeyError, TypeError:
        return None


def cleanup(primary: Path, current: Path | None, *, dry_run: bool) -> list[str]:
    """Remove what is merged in one repository and return one line per removal."""
    merged = merged_heads(primary)
    worktrees = linked_worktrees(primary)
    checked_out = {worktree.branch for worktree in worktrees} | {current_branch(primary)}
    workspaces = herdr_workspaces(primary)
    report = []
    removed = set()
    for worktree in worktrees:
        if worktree.path in {primary, current} or not is_merged(primary, worktree.branch, merged):
            continue
        if not worktree_is_clean(primary, worktree):
            continue
        removed.add(worktree.path)
        report.append(f"remove worktree {worktree.path} and branch {worktree.branch}")
        if not dry_run:
            remove_worktree(primary, worktree, workspaces.get(worktree.path))
            run("git", "branch", "-D", "--", worktree.branch, cwd=primary)
    for branch in local_branches(primary) - checked_out:
        if not is_merged(primary, branch, merged):
            continue
        report.append(f"remove branch {branch}")
        if not dry_run:
            run("git", "branch", "-D", "--", branch, cwd=primary)
    if report:
        report += fast_forward_default_branch(primary, dry_run=dry_run)
    remaining = worktrees if dry_run else linked_worktrees(primary)
    if removed and not any(
        worktree.path != primary and (not dry_run or worktree.path not in removed) for worktree in remaining
    ):
        report += close_primary_workspaces(primary, dry_run=dry_run)
    return report


def worktree_is_clean(primary: Path, worktree: Worktree) -> bool:
    if not worktree.admin_dir or git_file_target(worktree.path) != worktree.admin_dir:
        return False
    try:
        if (
            (worktree.admin_dir / (worktree.admin_dir / "commondir").read_text().strip()).resolve() != primary / ".git"
            or Path((worktree.admin_dir / "gitdir").read_text().strip()).resolve() != worktree.path / ".git"
            or (worktree.admin_dir / "config.worktree").exists()
        ):
            return False
    except OSError:
        return False
    command = ("git", f"--git-dir={worktree.admin_dir}", f"--work-tree={worktree.path}")
    if any(
        entry.startswith("160000 ") for entry in run(*command, "ls-files", "--stage", "-z", cwd=primary).split("\0")
    ):
        return False
    return not run(
        *command,
        "-c",
        "diff.ignoreSubmodules=all",
        "status",
        "--porcelain",
        "--ignore-submodules=all",
        cwd=primary,
    )


def recorded_primary_workspaces(primary: Path) -> dict[str, dict]:
    """Find primary workspaces created by any registered agent session."""
    base = session_store.state_directory()
    if not base.is_dir():
        return {}
    workspaces = {}
    for directory in session_store.record_directories(base):
        try:
            record = session_store.load(directory)
            owned = herdr_ownership.entries(record, "workspaces")
        except OSError, ValueError, KeyError, TypeError:
            continue
        workspaces.update({key: entry for key, entry in owned.items() if Path(entry["path"]).resolve() == primary})
    return workspaces


def close_primary_workspaces(primary: Path, *, dry_run: bool) -> list[str]:
    """Close an agent-created primary only while its identity matches and no agent occupies it."""
    try:
        identities = idle_primary_workspaces(primary)
    except OSError, subprocess.SubprocessError, ValueError, TypeError:
        return []
    if dry_run:
        return [f"close primary workspace {identity} ({primary})" for identity in identities]
    report = []
    for identity in identities:
        try:
            run("herdr", "workspace", "close", identity, cwd=primary)
        except subprocess.CalledProcessError as error:
            report.append(f"failed to close primary workspace {identity} ({primary}): {error}")
            continue
        report.append(f"close primary workspace {identity} ({primary})")
    return report


def idle_primary_workspaces(primary: Path) -> list[str]:
    owned = recorded_primary_workspaces(primary)
    if not owned:
        return []
    identities = []
    for workspace in herdr_items("workspace"):
        identity = workspace.get("workspace_id")
        if not isinstance(identity, str) or not identity:
            continue
        entry = owned.get(identity)
        if (
            not entry
            or workspace.get("label") != entry["label"]
            or herdr_ownership.live_path(workspace) != str(primary)
        ):
            continue
        if primary_workspace_idle(identity, entry):
            identities.append(identity)
    return identities


def primary_workspace_idle(identity: str, entry: dict) -> bool:
    panes = herdr_items("pane", "--workspace", identity)
    if not any(pane.get("terminal_id") == entry["terminal_id"] for pane in panes):
        return False
    terminals = {pane["terminal_id"] for pane in panes if pane.get("terminal_id")}
    pane_ids = {pane["pane_id"] for pane in panes if pane.get("pane_id")}
    return not any(
        agent.get("workspace_id") == identity
        or agent.get("terminal_id") in terminals
        or (not agent.get("workspace_id") and agent.get("pane_id") in pane_ids)
        for agent in herdr_items("agent")
    )


def herdr_items(kind: str, *arguments: str) -> list[dict]:
    """Require an explicit listing; missing or malformed live state cannot prove a workspace idle."""
    items = herdr_ownership.herdr_result(kind, "list", *arguments).get(kind + "s")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError(f"Invalid Herdr {kind} listing")
    return items


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
    fetch = ("git", "fetch", "--quiet", "--", "origin", f"{branch}:{branch}")
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
    return run("git", "rev-parse", "--verify", "--end-of-options", f"refs/heads/{branch}", cwd=primary) in merged.get(
        branch, set()
    )


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
    admin_dirs = {
        Path((admin / "gitdir").read_text().strip()).parent.resolve(): admin.resolve()
        for admin in (primary / ".git/worktrees").glob("*")
        if (admin / "gitdir").is_file()
    }
    worktrees = []
    for block in run("git", "worktree", "list", "--porcelain", cwd=primary).split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        branch = fields.get("branch", "").removeprefix("refs/heads/")
        if "worktree" in fields:
            path = Path(fields["worktree"]).resolve()
            worktrees.append(Worktree(path, branch, admin_dirs.get(path)))
    return worktrees


def git_file_target(path: Path) -> Path | None:
    try:
        if (path / ".git").is_symlink():
            return None
        content = (path / ".git").read_text().strip()
        if content.startswith("gitdir: "):
            return (path / content.removeprefix("gitdir: ")).resolve()
    except OSError:
        pass
    return None


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
    """Remove a checkout already verified clean, closing its Herdr workspace when one is open."""
    run("git", "worktree", "remove", "--force", "--", str(worktree.path), cwd=primary)
    if workspace:
        run("herdr", "workspace", "close", workspace, cwd=primary)


def run(*command: str, cwd: Path) -> str:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    if command[0] == "git":
        environment.update(GIT_COMMON_DIR=str(cwd / ".git"), GIT_CONFIG_NOSYSTEM="1")
        location = (
            ()
            if command[1].startswith("--git-dir=")
            else (
                f"--git-dir={cwd / '.git'}",
                f"--work-tree={cwd}",
            )
        )
        command = (
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "extensions.worktreeConfig=false",
            *(
                ("-c", "filter.lfs.process=", "-c", "filter.lfs.clean=", "-c", "filter.lfs.smudge=")
                if not location
                else ()
            ),
            *location,
            *command[1:],
        )
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        timeout=TIMEOUT_SECONDS,
        env=environment,
    ).stdout.strip()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
