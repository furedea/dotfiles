"""Confirm an immediate squash merge without hiding command failures or unsafe cleanup."""

import os
import subprocess
import sys
import termios
import tty


def read_key() -> str:
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
    print("\nPress Enter or Esc to close...", end="", flush=True)
    while read_key() not in {"", "\n", "\r", "\x1b", "\x03"}:
        pass
    print()


def confirm_merge() -> bool:
    answer = read_key()
    if answer in {"\n", "\r"}:
        return True
    print("\nCancelled.")
    if answer not in {"", "\x1b", "\x03"}:
        wait_for_close()
    return False


def checked_out(branch: str, worktrees: str) -> bool:
    return f"branch refs/heads/{branch}" in worktrees.splitlines()


def capture(arguments: list[str]) -> str:
    return subprocess.check_output(arguments, text=True).strip()


def merge(repository: str) -> int:
    git = os.environ.get("GIT_BIN", "git")
    gh = os.environ.get("GH_BIN", "gh")
    root = capture([git, "-C", repository, "rev-parse", "--show-toplevel"])
    os.chdir(root)
    if capture([git, "-C", root, "status", "--porcelain=v1"]):
        print("Cannot merge: working tree has uncommitted changes.")
        return 1
    fields = capture(
        [
            gh,
            "pr",
            "view",
            "--json",
            "number,title,baseRefName,headRefName",
            "--jq",
            "[.number, .title, .baseRefName, .headRefName] | @tsv",
        ]
    )
    number, title, base, head = fields.split("\t")
    commit = capture([git, "-C", root, "rev-parse", "HEAD"])
    worktrees = capture([git, "-C", root, "worktree", "list", "--porcelain"])
    arguments = [gh, "pr", "merge", "--squash"]
    if checked_out(base, worktrees):
        cleanup = f"keep this worktree and local branch; {base} is checked out elsewhere."
    else:
        arguments.append("--delete-branch")
        cleanup = f"delete the merged branch and switch to {base}."
    arguments += ["--match-head-commit", commit]
    print(f"PR #{number}: {title}\n{head} -> {base}\n\nLocal cleanup: {cleanup}\n")
    print("Enter / Ctrl+M  Squash and merge now\nEsc             Cancel", flush=True)
    if not confirm_merge():
        return 0
    print(flush=True)
    return subprocess.run(arguments, check=False).returncode


def main(arguments: list[str]) -> int:
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
