"""Inspect a conservative shell subset using shfmt's parser, never by executing input."""

from dataclasses import dataclass, replace
from collections.abc import Iterator
import json
from pathlib import Path
import re
import shlex
import subprocess
from typing import Self


COMMAND_PREVIEW_LIMIT = 200
ALLOWED_NODES = frozenset(
    {None, "File", "CallExpr", "BinaryCmd", "Subshell", "Block", "Lit", "SglQuoted", "DblQuoted", "TimeClause"}
)
SHELLS = frozenset({"bash", "sh", "zsh"})
COMMAND_LOOKUP = frozenset({"-v", "-V"})
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# Process wrappers run their trailing arguments as a command. Each entry lists the flags without an
# operand and the options whose operand is the next token; unknown options are refused, not skipped.
WRAPPERS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "caffeinate": (frozenset({"-d", "-i", "-m", "-s", "-u"}), frozenset({"-t", "-w"})),
    "command": (frozenset({"-p"}), frozenset()),
    "env": (frozenset({"-i", "--ignore-environment", "-0", "--null"}), frozenset({"-u", "--unset", "-C", "--chdir"})),
    "exec": (frozenset({"-c", "-l"}), frozenset({"-a"})),
    "nice": (frozenset(), frozenset({"-n", "--adjustment"})),
    "nohup": (frozenset(), frozenset()),
    "time": (frozenset({"-p", "-l", "-h", "-a", "--portability"}), frozenset({"-o", "-f", "--output", "--format"})),
    "timeout": (
        frozenset({"--preserve-status", "--foreground", "-v"}),
        frozenset({"-k", "--kill-after", "-s", "--signal"}),
    ),
    "xargs": (
        frozenset({"-0", "-r", "-t", "-p", "-x", "-o", "--null", "--no-run-if-empty", "--verbose", "--interactive"}),
        frozenset(
            {"-n", "-I", "-L", "-P", "-s", "-d", "-E", "-a", "--max-args", "--replace", "--max-lines", "--max-procs"}
        ),
    ),
}


class UnsupportedSyntax(ValueError):
    """The command cannot be statically inspected by this supplementary guard."""


@dataclass(frozen=True, slots=True)
class Command:
    """A parsed literal command and its original source representation."""

    raw: str
    arguments: tuple[str, ...]
    wrapper_depth: int = 0
    redirections: tuple[str, ...] = ()
    words: tuple[str, ...] = ()
    trailer: str = ""

    def __post_init__(self) -> None:
        if not self.words:
            object.__setattr__(self, "words", self.arguments)

    def rebased(self, index: int, head: tuple[str, ...] = (), depth: int | None = None) -> Self:
        """Keep the arguments from one index onward, optionally behind a canonical head or one wrapper deeper."""
        words = (*head, *self.words[index:])
        raw = " ".join((*words, self.trailer)).rstrip()
        wrapper_depth = self.wrapper_depth if depth is None else depth
        return replace(
            self, raw=raw, arguments=(*head, *self.arguments[index:]), wrapper_depth=wrapper_depth, words=words
        )


def command_preview(source: str) -> str:
    """Bound guard diagnostics without repeating inline script bodies."""
    lines = source.splitlines()
    first = lines[0] if lines else ""
    preview = first[:COMMAND_PREVIEW_LIMIT]
    if len(first) > COMMAND_PREVIEW_LIMIT or len(lines) > 1:
        return preview + "\nRemaining command text omitted."
    return preview


def parse(source: str, depth: int = 0) -> tuple[Command, ...]:
    """Parse literal commands, including static shell and process wrappers, and reject unknown syntax."""
    if not source.strip():
        return ()
    if depth > 8:
        raise UnsupportedSyntax("shell wrapper nesting exceeds the inspection limit")
    records = tuple(nodes(syntax_tree(source)))
    owners = {id(node["Cmd"]): node for node in records if isinstance(node.get("Cmd"), dict)}
    if any(node.get("Hdoc") for node in records):
        raise UnsupportedSyntax("heredoc syntax requires explicit review")
    if any(node.get("Type") not in ALLOWED_NODES for node in records):
        raise UnsupportedSyntax("dynamic or unsupported shell syntax requires explicit review")
    data = source.encode()
    commands: list[Command] = []
    for node in records:
        if node.get("Type") != "CallExpr" or not node.get("Args"):
            continue
        command = literal_command(node, owners.get(id(node), node), data, depth)
        commands.append(command)
        commands.extend(unwrapped(command))
        if script := shell_script(commands[-1].arguments):
            commands.extend(parse(script, commands[-1].wrapper_depth + 1))
    return tuple(commands)


def syntax_tree(source: str) -> dict:
    """Obtain shfmt's syntax tree, refusing to guess about input it cannot parse."""
    try:
        result = subprocess.run(
            ["shfmt", "-ln", "bash", "--to-json"], input=source, text=True, capture_output=True, timeout=5, check=False
        )
        if result.returncode:
            raise UnsupportedSyntax("unsupported or invalid shell syntax")
        return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        raise UnsupportedSyntax("shell parser unavailable; command cannot be validated") from error


def nodes(value: object) -> Iterator[dict]:
    """Walk parser records without interpreting position metadata as executable code."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def literal_command(node: dict, owner: dict, data: bytes, depth: int) -> Command:
    """Decode one call expression together with the statement text that owns it."""
    raw = source_text(owner, data).strip()
    if owner.get("Semicolon") and raw.endswith(";"):
        raw = raw[:-1].rstrip()
    if owner.get("Background") and raw.endswith("&"):
        raw = raw[:-1].rstrip()
    redirects = owner.get("Redirs", [])
    return Command(
        raw,
        tuple(literal_word(word, data) for word in node["Args"]),
        depth,
        tuple(literal_word(redirect["Word"], data) for redirect in redirects if redirect.get("Word")),
        tuple(source_text(word, data) for word in node["Args"]),
        " ".join(source_text(redirect, data) for redirect in redirects),
    )


def source_text(node: dict, source: bytes) -> str:
    """Use byte offsets so non-ASCII input cannot shift command boundaries."""
    return source[node["Pos"]["Offset"] : node["End"]["Offset"]].decode()


def literal_word(word: dict, source: bytes) -> str:
    """Decode quoting only after the syntax tree has excluded executable expansions."""
    for part in nodes(word):
        if part.get("Dollar"):
            raise UnsupportedSyntax("dollar-quoted shell words require explicit review")
        if part.get("Type") not in {None, "Lit", "SglQuoted", "DblQuoted"}:
            raise UnsupportedSyntax("shell expansions require explicit review")
    for part in word.get("Parts", []):
        if part.get("Type") == "Lit" and re.search(r"(?<!\\)[*?\[]|^~", part.get("Value", "")):
            raise UnsupportedSyntax("unquoted shell expansion requires explicit review")
    values = shlex.split(source_text(word, source), posix=True)
    if len(values) != 1:
        raise UnsupportedSyntax("a shell word could not be decoded unambiguously")
    return values[0]


def unwrapped(command: Command) -> list[Command]:
    """Peel process wrappers so policy sees the program they eventually run."""
    exposed: list[Command] = []
    while (index := wrapped_index(command.arguments)) is not None:
        command = command.rebased(index, depth=command.wrapper_depth + 1)
        exposed.append(command)
    return exposed


def wrapped_index(arguments: tuple[str, ...]) -> int | None:
    """Locate the command a process wrapper runs, or None when the call is not a wrapper invocation."""
    name = Path(arguments[0]).name
    if name not in WRAPPERS:
        return None
    flags, valued = WRAPPERS[name]
    index = 1
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            index += 1
            break
        if name == "command" and token in COMMAND_LOOKUP:
            return None
        if token in valued:
            index += 2
        elif (name == "env" and ASSIGNMENT.match(token)) or is_flag(name, token, flags, valued):
            index += 1
        elif token.startswith("-"):
            raise UnsupportedSyntax(f"{name} option requires explicit review: {token}")
        else:
            break
    if name == "timeout":
        index += 1
    return index if index < len(arguments) else None


def is_flag(name: str, token: str, flags: frozenset[str], valued: frozenset[str]) -> bool:
    """Recognize options that carry no separate operand, including attached-value short forms."""
    if token in flags:
        return True
    if token.startswith("--"):
        key, _, value = token.partition("=")
        return bool(value) and key in valued
    if len(token) > 2 and token[:2] in valued:
        return True
    if name == "nice":
        return token[1:].isdigit()
    return name == "caffeinate" and re.fullmatch(r"-[dimsu]+", token) is not None


def shell_script(arguments: tuple[str, ...]) -> str:
    """Return the literal script that eval or a shell -c invocation runs, or an empty string."""
    executable = Path(arguments[0]).name
    if executable == "eval":
        return " ".join(arguments[1:])
    if executable not in SHELLS:
        return ""
    option = next(
        (
            index
            for index, argument in enumerate(arguments[1:], 1)
            if argument.startswith("-") and not argument.startswith("--") and "c" in argument
        ),
        None,
    )
    if option is None:
        return ""
    if option + 1 >= len(arguments):
        raise UnsupportedSyntax("shell wrapper has no literal command")
    return arguments[option + 1]
