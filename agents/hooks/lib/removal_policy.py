"""Judge rm by whether every target is an absolute literal path inside a temporary directory.

A relative path depends on a working directory the command may change, and a word that the shell
expands, such as zsh's =name, names a path the hook cannot see; git rm covers tracked files.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re

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
# A target passes only in characters every shell reads alike, so the hook and the shell see one path.
PLAIN_PATH = re.compile(r"[A-Za-z0-9._/@+,:%-]+")
# A root counts only when it really lies in a system temporary area, not when it links elsewhere.
SYSTEM_TEMPORARY_AREAS = (Path("/private/tmp"), Path("/private/var/folders"), Path("/tmp"))
# Commands that only read, so beside them an rm target stays as the hook sees it. rg is absent since
# its --pre runs a program, and time since its -o writes a file.
READERS = frozenset({"[", "cat", "echo", "false", "grep", "head", "ls", "printf", "pwd", "tail", "test", "true", "wc"})
INERT_WRAPPERS = frozenset(shell_syntax.WRAPPERS) - {"time"}


@dataclass(frozen=True, slots=True)
class Removal:
    """One rm invocation; `targets` is None unless every target is an absolute literal path.

    `settled` is False when another command could write, move, or relink a target first.
    """

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
        """Whether a recursive removal reaches past settled temporary paths; such a removal is denied."""
        return self.recursive and not self.is_accounted_for


def removal(command: shell_syntax.Command, settled: bool) -> Removal | None:
    """Read a canonical rm command whose targets count only as absolute literal paths."""
    if command.arguments[0] != "rm":
        return None
    recursive, operands = False, []
    hidden = command.appends_input
    options_ended = False
    # Options are read from the decoded words, so quoting or escaping cannot hide a recursive flag.
    for word, source, dynamic in zip(command.arguments[1:], command.words[1:], command.dynamic[1:], strict=True):
        if dynamic:
            hidden = True
        elif not options_ended and word == "--":
            options_ended = True
        elif not options_ended and word.startswith("-") and word != "-":
            recursive |= is_recursive(word)
            hidden |= not is_option(word)
        else:
            operands.append(word)
            hidden |= source.startswith("~") or "$" in source or "\\" in source or not PLAIN_PATH.fullmatch(word)
    if hidden or not operands or not all(Path(word).is_absolute() for word in operands):
        return Removal(recursive, None, settled)
    return Removal(recursive, tuple(Path(word) for word in operands), settled)


def is_settled(commands: tuple[shell_syntax.Command, ...]) -> bool:
    """Whether every segment of the command leaves rm targets as the hook sees them."""
    return all(is_inert(command) for command in commands)


def is_inert(command: shell_syntax.Command) -> bool:
    """Whether a segment leaves rm targets alone: rm itself, a wrapper whose program is judged on its
    own, or a reader without output redirections."""
    if command.program_is_dynamic or command.writes:
        return False
    name = Path(command.arguments[0]).name
    return name == "rm" or name in INERT_WRAPPERS or name in READERS


def is_recursive(option: str) -> bool:
    if option.startswith("--"):
        return option == "--recursive"
    return bool(set(option[1:]) & {"r", "R"})


def is_option(word: str) -> bool:
    if word.startswith("--"):
        return word in LONG_FLAGS or word.startswith("--interactive=")
    return set(word[1:]) <= SHORT_FLAGS


def is_temporary(target: Path) -> bool:
    """Whether the target lies strictly inside a trusted root, both as written and once symlinks resolve."""
    written = Path(os.path.normpath(target))
    resolved = Path(os.path.realpath(target))
    roots = trusted_roots()
    return any(is_inside(written, root) for pair in roots for root in pair) and any(
        is_inside(resolved, resolved_root) for _, resolved_root in roots
    )


def trusted_roots() -> tuple[tuple[Path, Path], ...]:
    """The scratchpad root and TMPDIR, as written and resolved, when they resolve into a system temporary area."""
    candidates = (SCRATCH_ROOT, Path(os.environ.get("TMPDIR", "")))
    pairs = ((Path(os.path.normpath(root)), Path(os.path.realpath(root))) for root in candidates if root.is_absolute())
    return tuple(
        (written, resolved)
        for written, resolved in pairs
        if any(is_inside(resolved, area) for area in SYSTEM_TEMPORARY_AREAS)
    )


def is_inside(path: Path, root: Path) -> bool:
    return path != root and path.is_relative_to(root)
