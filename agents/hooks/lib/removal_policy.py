"""Judge rm by whether every target is a literal path inside a temporary directory; git rm covers tracked files."""

from dataclasses import dataclass
import os
from pathlib import Path

import shell_syntax


TREE_REASON = (
    "Do not remove directory trees outside a temporary directory from an agent session; "
    "Git cannot restore untracked files."
)
FILE_REASON = "removing files outside a temporary directory needs review; use git rm for tracked files"
# Claude Code points each sandboxed command's TMPDIR, including session scratchpads, below this root.
SCRATCH_ROOT = Path(f"/private/tmp/claude-{os.getuid()}")
SHORT_FLAGS = frozenset("dfiIPRrvWx")
LONG_FLAGS = frozenset(
    {"--dir", "--force", "--interactive", "--one-file-system", "--preserve-root", "--recursive", "--verbose"}
)
DIRECTORY_CHANGES = frozenset({"cd", "pushd", "popd"})
# Commands that only read, so beside them an rm target stays as the hook sees it. rg is absent since
# its --pre runs a program, and time since its -o writes a file.
READERS = frozenset({"[", "cat", "echo", "false", "grep", "head", "ls", "printf", "pwd", "tail", "test", "true", "wc"})
INERT_WRAPPERS = frozenset(shell_syntax.WRAPPERS) - {"time"}


@dataclass(frozen=True, slots=True)
class Workspace:
    """What the rest of one command leaves fixed: the working directory, if known, and the file system.

    `settled` is False when another command could write, move, or relink an rm target first.
    """

    directory: Path | None
    settled: bool


@dataclass(frozen=True, slots=True)
class Removal:
    """One rm invocation; `targets` is None unless every target is a literal path the hook can resolve."""

    recursive: bool
    targets: tuple[Path, ...] | None
    settled: bool = True

    @property
    def is_temporary(self) -> bool:
        return bool(self.targets) and all(is_temporary(target) for target in self.targets)

    @property
    def is_accounted_for(self) -> bool:
        """Whether every target is temporary and nothing else in the command can change that first."""
        return self.settled and self.is_temporary

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
    for word, source, dynamic in zip(command.arguments[1:], command.words[1:], command.dynamic[1:], strict=True):
        if dynamic or source.startswith("~") or "$" in source:
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
    if hidden or not operands or (directory is None and not all(Path(word).is_absolute() for word in operands)):
        return Removal(recursive, None, workspace.settled)
    targets = tuple(Path(os.path.join(directory or "/", word)) for word in operands)
    return Removal(recursive, targets, workspace.settled)


def workspace(payload: dict, commands: tuple[shell_syntax.Command, ...]) -> Workspace:
    """Judge the whole command once: whether the working directory and the file system stay put."""
    known = not any(changes_directory(command) for command in commands)
    return Workspace(starting_directory(payload) if known else None, all(is_inert(command) for command in commands))


def starting_directory(payload: dict) -> Path:
    """Where the command starts: the tool's own workdir, if it names one, resolved against the session cwd."""
    cwd = payload.get("cwd")
    session = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
    values = payload.get("tool_input")
    workdir = values.get("workdir") if isinstance(values, dict) else None
    return session / workdir if isinstance(workdir, str) and workdir else session


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
    return name == "rm" or name in INERT_WRAPPERS or name in READERS


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
