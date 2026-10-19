"""Judge rm by whether a temporary directory or Git accounts for everything it removes."""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

import shell_syntax


TREE_REASON = (
    "Do not remove directory trees outside a temporary directory from an agent session; "
    "Git cannot restore untracked files."
)
FILE_REASON = "removing files that neither a temporary directory nor Git can restore needs review"
# Claude Code points each sandboxed command's TMPDIR, including session scratchpads, below this root.
SCRATCH_ROOT = Path(f"/private/tmp/claude-{os.getuid()}")
SHORT_FLAGS = frozenset("dfiIPRrvWx")
LONG_FLAGS = frozenset(
    {"--dir", "--force", "--interactive", "--one-file-system", "--preserve-root", "--recursive", "--verbose"}
)
DIRECTORY_CHANGES = frozenset({"cd", "pushd", "popd"})
# Characters Git reads as a wildcard or pathspec magic, so a name holding one may match another file.
PATHSPEC_SPECIALS = frozenset("*?[]\\:!")
# Commands that only read, so beside them an rm target stays as the hook sees it.
READERS = frozenset(
    {"[", "cat", "echo", "false", "grep", "head", "ls", "printf", "pwd", "rg", "tail", "test", "true", "wc"}
)


@dataclass(frozen=True, slots=True)
class Workspace:
    """What the rest of one command leaves fixed: the working directory, if known, and the file system.

    `settled` is False when another command could write, move, or relink an rm target first.
    """

    directory: Path | None
    settled: bool


@dataclass(frozen=True, slots=True)
class Removal:
    """One rm invocation; `targets` is None when a run-time word, input, or unknown option hides them."""

    recursive: bool
    targets: tuple[Path, ...] | None
    settled: bool = True

    @property
    def is_temporary(self) -> bool:
        return bool(self.targets) and all(is_temporary(target) for target in self.targets)

    @property
    def is_accounted_for(self) -> bool:
        """Whether every target is temporary or, for a plain removal, restorable from Git, and stays so."""
        if not self.settled:
            return False
        if self.is_temporary:
            return True
        return not self.recursive and bool(self.targets) and all(is_restorable(target) for target in self.targets)

    @property
    def removes_unaccounted_tree(self) -> bool:
        return self.recursive and not self.is_temporary


def removal(command: shell_syntax.Command, workspace: Workspace) -> Removal | None:
    """Read a canonical rm command, resolving relative targets against the known working directory."""
    if command.arguments[0] != "rm":
        return None
    recursive, operands = False, []
    hidden = command.appends_input
    options_ended = False
    for word, dynamic in zip(command.arguments[1:], command.dynamic[1:], strict=True):
        if dynamic:
            hidden = True
        elif options_ended or word == "-" or not word.startswith("-"):
            operands.append(word)
        elif word == "--":
            options_ended = True
        elif is_option(word):
            recursive |= word == "--recursive" or (not word.startswith("--") and bool(set(word) & {"r", "R"}))
        else:
            hidden = True
    directory = workspace.directory
    hidden |= any(PATHSPEC_SPECIALS & set(word) for word in operands)
    if hidden or not operands or (directory is None and not all(Path(word).is_absolute() for word in operands)):
        return Removal(recursive, None, workspace.settled)
    targets = tuple(Path(os.path.join(directory or "/", word)) for word in operands)
    return Removal(recursive, targets, workspace.settled)


def workspace(payload_directory: object, commands: tuple[shell_syntax.Command, ...]) -> Workspace:
    """Judge the whole command once: whether the working directory and the file system stay put."""
    known = not any(changes_directory(command) for command in commands)
    directory = Path(payload_directory) if isinstance(payload_directory, str) and payload_directory else Path.cwd()
    return Workspace(directory if known else None, all(is_inert(command) for command in commands))


def changes_directory(command: shell_syntax.Command) -> bool:
    """Whether a segment may run rm, or anything after it, from another directory."""
    if command.program_is_dynamic:
        return True
    name, rest = Path(command.arguments[0]).name, command.arguments[1:]
    if name == "builtin":
        return bool(rest) and rest[0] in DIRECTORY_CHANGES
    if name == "env":
        return any(word.startswith(("-C", "--chdir")) for word in rest)
    return name in DIRECTORY_CHANGES or name in {"source", "."}


def is_inert(command: shell_syntax.Command) -> bool:
    """Whether a segment leaves rm targets alone: rm itself, a wrapper whose program is judged on its
    own, or a reader without output redirections."""
    if command.program_is_dynamic or command.writes:
        return False
    name = Path(command.arguments[0]).name
    if name == "env":
        return not changes_directory(command)
    return name == "rm" or name in shell_syntax.WRAPPERS or name in READERS


def is_option(word: str) -> bool:
    if word.startswith("--"):
        return word in LONG_FLAGS or word.startswith("--interactive=")
    return set(word[1:]) <= SHORT_FLAGS


def is_temporary(target: Path) -> bool:
    """Whether the resolved target lies strictly inside a temporary root, so symlinks cannot lead out."""
    resolved = Path(os.path.realpath(target))
    return any(resolved != root and resolved.is_relative_to(root) for root in temporary_roots())


def temporary_roots() -> tuple[Path, ...]:
    """The scratchpad root and TMPDIR, ignoring a TMPDIR that contains the home directory."""
    candidates = [SCRATCH_ROOT, Path(os.environ.get("TMPDIR", ""))]
    roots = (Path(os.path.realpath(candidate)) for candidate in candidates if candidate.is_absolute())
    home = Path(os.path.realpath(Path.home()))
    return tuple(root for root in roots if not home.is_relative_to(root))


def is_restorable(target: Path) -> bool:
    """A regular tracked file whose working, staged, and HEAD contents are one blob comes back with git restore.

    The raw bytes are hashed rather than diffed: Git skips its change check for files flagged
    assume-unchanged or skip-worktree, which never count as restorable, and a clean filter could
    drop uncommitted content before hashing.
    """
    if target.is_symlink() or not target.is_file():
        return False
    entries = git(target.parent, "ls-files", "-v", "-s", "--", target.name).splitlines()
    if len(entries) != 1:
        return False
    tag, mode, staged, _ = entries[0].split(" ", 3)
    if tag != "H" or mode not in {"100644", "100755"}:
        return False
    committed = git(target.parent, "rev-parse", "--verify", "--quiet", f"HEAD:./{target.name}")
    working = git(target.parent, "hash-object", "--no-filters", "--", target.name)
    return staged == committed == working


def git(directory: Path, *arguments: str) -> str:
    """Run a Git query and return its trimmed output, or an empty string when it fails."""
    try:
        result = subprocess.run(
            ["git", "--literal-pathspecs", "-C", str(directory), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""
