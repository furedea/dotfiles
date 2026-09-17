"""Evaluate explicit Git operations without relying on whitespace-based argument parsing."""

from pathlib import Path
import subprocess


PROTECTED_BRANCHES = {"main", "master"}
DESTRUCTIVE_VERBS = {"clean", "filter-branch", "filter-repo", "replace"}
FORCE_FLAGS = {"-f", "--force"}


def branch(arguments: tuple[str, ...] = ()) -> str:
    """Read the current branch, retaining any supported global Git path options."""
    try:
        return subprocess.check_output(
            ["git", *arguments, "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("cannot determine the implicit Git push target") from error


def git_arguments(arguments: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Separate supported global Git options from the subcommand."""
    index = 1
    while index < len(arguments) and arguments[index].startswith("-"):
        option = arguments[index]
        if option in {"-C", "-c", "--git-dir", "--work-tree"}:
            index += 2
        elif option.startswith(("--git-dir=", "--work-tree=", "--config-env=")) or option in {
            "--no-pager",
            "--paginate",
            "--no-optional-locks",
        }:
            index += 1
        else:
            raise ValueError(f"unsupported global Git option requires review: {option}")
    return arguments[1:index], arguments[index:]


def push_reason(arguments: tuple[str, ...], globals_: tuple[str, ...]) -> str:
    """Reject unleased force pushes and protected destinations, including implicit destinations."""
    flags = {argument.split("=", 1)[0] for argument in arguments}
    if flags & FORCE_FLAGS:
        return "force-push flag detected"
    if "--force-with-lease" in flags and "--force-if-includes" not in flags:
        return "force-with-lease without --force-if-includes detected"
    positional: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            positional.extend(arguments[index + 1 :])
            break
        if argument in {"--repo", "--receive-pack", "--exec"}:
            index += 2
            continue
        if not argument.startswith("-"):
            positional.append(argument)
        index += 1
    refspecs = positional[1:]
    if not refspecs:
        destination = branch(globals_)
        return f"push target is '{destination}'" if destination in PROTECTED_BRANCHES else ""
    for refspec in refspecs:
        if refspec.startswith("+"):
            return "'+refspec' force push detected"
        destination = refspec.rsplit(":", 1)[-1]
        if destination == "HEAD":
            destination = branch(globals_)
        destination = destination.removeprefix("refs/heads/")
        if destination in PROTECTED_BRANCHES:
            return f"push target is '{destination}'"
    return ""


def reason(arguments: tuple[str, ...]) -> str:
    """Return the independently forbidden operation, or no supplementary objection."""
    if not arguments:
        return ""
    executable = Path(arguments[0]).name
    if executable == "gh" and arguments[1:3] == ("pr", "merge") and "--admin" in arguments[3:]:
        return "gh pr merge --admin bypasses branch protection"
    if executable != "git":
        return ""
    globals_, command = git_arguments(arguments)
    if not command:
        return ""
    verb, *remaining = command
    options = {argument.split("=", 1)[0] for argument in remaining}
    if verb == "push":
        return push_reason(tuple(remaining), globals_)
    destructive = verb in DESTRUCTIVE_VERBS
    destructive |= verb == "worktree" and bool(remaining) and remaining[0] in {"move", "repair"}
    destructive |= verb == "worktree" and remaining[:1] == ["remove"] and bool(options & FORCE_FLAGS)
    destructive |= verb == "reflog" and bool(remaining) and remaining[0] in {"delete", "expire"}
    dangerous_options = {
        "branch": {"-D"},
        "rm": FORCE_FLAGS,
        "mv": FORCE_FLAGS,
        "symbolic-ref": {"-d", "--delete"},
        "update-ref": {"-d", "--delete"},
        "gc": {"--prune"},
        "reset": {"--hard", "--keep", "--merge"},
        "switch": {"-f", "--force", "-C", "--discard-changes"},
        "checkout": {"-f", "--force", "-B", "--", "."},
    }
    destructive |= bool(options & dangerous_options.get(verb, set()))
    if verb == "restore":
        destructive = not bool(options & {"--staged", "-S"}) or bool(options & {"--worktree", "-W", "--source", "-s"})
    return f"destructive git operation: {verb}" if destructive else ""
