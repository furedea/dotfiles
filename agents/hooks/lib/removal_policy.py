"""Judge rm by whether a temporary directory or Git accounts for everything it removes."""

from collections.abc import Iterable
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
CHDIR_OPTIONS = frozenset({"-C", "--chdir"})


@dataclass(frozen=True, slots=True)
class Removal:
    """One rm invocation; `targets` is None when a run-time word, input, or unknown option hides them."""

    recursive: bool
    targets: tuple[Path, ...] | None

    @property
    def is_temporary(self) -> bool:
        return bool(self.targets) and all(is_temporary(target) for target in self.targets)

    @property
    def is_accounted_for(self) -> bool:
        """Whether every target is temporary or, for a plain removal, restorable from Git."""
        if self.is_temporary:
            return True
        return not self.recursive and bool(self.targets) and all(is_restorable(target) for target in self.targets)

    @property
    def removes_unaccounted_tree(self) -> bool:
        return self.recursive and not self.is_temporary


def removal(command: shell_syntax.Command, directory: Path | None) -> Removal | None:
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
    if hidden or not operands or (directory is None and not all(Path(word).is_absolute() for word in operands)):
        return Removal(recursive, None)
    return Removal(recursive, tuple(Path(os.path.join(directory or "/", word)) for word in operands))


def working_directory(payload_directory: object, commands: Iterable[shell_syntax.Command]) -> Path | None:
    """The directory relative targets name, or None once any segment may have changed it."""
    for command in commands:
        name = Path(command.arguments[0]).name
        if name in DIRECTORY_CHANGES or (name == "env" and CHDIR_OPTIONS & set(command.arguments)):
            return None
    return Path(payload_directory) if isinstance(payload_directory, str) and payload_directory else Path.cwd()


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
    """A tracked file whose staged and working contents match HEAD comes back with git restore."""
    if target.is_dir() or not (target.is_file() or target.is_symlink()):
        return False
    return git(target.parent, "ls-files", "--error-unmatch", "--", target.name) and git(
        target.parent, "diff", "--quiet", "HEAD", "--", target.name
    )


def git(directory: Path, *arguments: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), *arguments],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0
