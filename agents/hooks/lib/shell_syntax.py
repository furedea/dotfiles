"""Inspect a conservative shell subset using shfmt's parser, never by executing input."""

from dataclasses import dataclass
from collections.abc import Iterator
import json
from pathlib import Path
import re
import shlex
import subprocess


class UnsupportedSyntax(ValueError):
    """The command cannot be statically inspected by this supplementary guard."""


@dataclass(frozen=True, slots=True)
class Command:
    """A parsed literal command and its original source representation."""

    raw: str
    arguments: tuple[str, ...]
    wrapper_depth: int = 0
    redirections: tuple[str, ...] = ()


def nodes(value: object) -> Iterator[dict]:
    """Walk parser records without interpreting position metadata as executable code."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


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


def parse(source: str, depth: int = 0) -> tuple[Command, ...]:
    """Parse literal commands, including static shell wrappers, and reject unknown syntax."""
    if not source.strip():
        return ()
    if depth > 8:
        raise UnsupportedSyntax("shell wrapper nesting exceeds the inspection limit")
    try:
        result = subprocess.run(
            ["shfmt", "-ln", "bash", "--to-json"], input=source, text=True, capture_output=True, timeout=5, check=False
        )
        if result.returncode:
            raise UnsupportedSyntax("unsupported or invalid shell syntax")
        tree = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        raise UnsupportedSyntax("shell parser unavailable; command cannot be validated") from error
    allowed = {None, "File", "CallExpr", "BinaryCmd", "Subshell", "Block", "Lit", "SglQuoted", "DblQuoted"}
    records = tuple(nodes(tree))
    owners = {id(node["Cmd"]): node for node in records if isinstance(node.get("Cmd"), dict)}
    if any(node.get("Type") not in allowed or node.get("Hdoc") for node in records):
        raise UnsupportedSyntax("dynamic or unsupported shell syntax requires explicit review")
    data = source.encode()
    commands: list[Command] = []
    for node in records:
        if node.get("Type") != "CallExpr":
            continue
        arguments = tuple(literal_word(word, data) for word in node.get("Args", []))
        if not arguments:
            continue
        owner = owners.get(id(node), node)
        raw = source_text(owner, data).strip()
        if owner.get("Semicolon") and raw.endswith(";"):
            raw = raw[:-1].rstrip()
        if owner.get("Background") and raw.endswith("&"):
            raw = raw[:-1].rstrip()
        redirections = tuple(
            literal_word(redirect["Word"], data) for redirect in owner.get("Redirs", []) if redirect.get("Word")
        )
        command = Command(raw, arguments, depth, redirections)
        commands.append(command)
        executable = Path(arguments[0]).name
        inner = ""
        if executable == "eval":
            inner = " ".join(arguments[1:])
        elif executable in {"bash", "sh", "zsh"}:
            option = next(
                (
                    index
                    for index, argument in enumerate(arguments[1:], 1)
                    if argument.startswith("-") and not argument.startswith("--") and "c" in argument
                ),
                None,
            )
            if option is not None:
                if option + 1 >= len(arguments):
                    raise UnsupportedSyntax("shell wrapper has no literal command")
                inner = arguments[option + 1]
        if inner:
            commands.extend(parse(inner, depth + 1))
    return tuple(commands)
