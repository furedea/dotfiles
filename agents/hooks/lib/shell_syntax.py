"""Inspect a conservative shell subset using shfmt's parser, never by executing input."""

from dataclasses import dataclass, replace
from collections.abc import Iterator
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from typing import Self


COMMAND_PREVIEW_LIMIT = 200
RUN_TIME_PLACEHOLDER = "_"
# Statements, words, arithmetic, loops and branches, and tests that the inspection understands.
ALLOWED_NODES = frozenset(
    {
        None,
        *(
            "File CallExpr BinaryCmd Subshell Block TimeClause DeclClause "
            "Word Lit SglQuoted DblQuoted ParamExp CmdSubst ProcSubst "
            "ArithmExp ArithmCmd BinaryArithm UnaryArithm ParenArithm "
            "ForClause WordIter CStyleLoop WhileClause IfClause CaseClause CaseItem "
            "TestClause BinaryTest UnaryTest ParenTest"
        ).split(),
    }
)
# Every command inside a substitution, clause, or function body is a CallExpr that parse judges on
# its own, so a body is judged where it is defined and a call by its own name; the substituted word
# itself is only known at run time.
SUBSTITUTIONS = frozenset({"CmdSubst", "ProcSubst", "ArithmExp"})
# A ParamExp other than the home directory makes its word a run-time word; Word is an operand inside it.
WORD_PARTS = frozenset({None, "Lit", "SglQuoted", "DblQuoted", "ParamExp", "Word"}) | SUBSTITUTIONS
QUOTED_PARTS = frozenset({"SglQuoted", "DblQuoted"})
HOME_PARAMETER = "HOME"
PARAMETER_MODIFIERS = ("Excl", "Length", "Width", "Index", "Slice", "Repl", "Exp")
SHELLS = frozenset({"bash", "sh", "zsh"})
COMMAND_LOOKUP = frozenset({"-v", "-V"})
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# All positional parameters, any single one (a digit), and every array element ([@] or [*]) can
# become any number of words, options included, even inside double quotes.
SPREADING = frozenset({"@", "*"})
# Parts that the shell splits into words, or expands into several, when they stand outside quotes.
SPLIT_PARTS = frozenset({"ParamExp", "CmdSubst", "ProcSubst", "ArithmExp"})
# A bracket opens a glob only when a closing bracket follows, so the test command `[` stays literal.
GLOB = re.compile(r"(?<!\\)[*?]|(?<!\\)\[.+\]")
# Brace expansion can pair braces across quoted parts, so any unquoted brace counts.
BRACES = frozenset("{}")
LINE_CONTINUATION = "\\\n"
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
    """A parsed literal command and its original source representation.

    `dynamic` flags arguments whose value is only known at run time (a glob or a parameter other
    than the home directory); such arguments carry their source text. `writes` lists the files
    that output redirections would create or overwrite. `appends_input` marks a command that xargs
    runs with further arguments read from its input. `spreading` flags arguments that may become
    several words at run time, options included.
    """

    raw: str
    arguments: tuple[str, ...]
    wrapper_depth: int = 0
    redirections: tuple[str, ...] = ()
    words: tuple[str, ...] = ()
    trailer: str = ""
    dynamic: tuple[bool, ...] = ()
    writes: tuple[str, ...] = ()
    appends_input: bool = False
    spreading: tuple[bool, ...] = ()

    def __post_init__(self) -> None:
        if not self.words:
            object.__setattr__(self, "words", self.arguments)
        if not self.dynamic:
            object.__setattr__(self, "dynamic", (False,) * len(self.arguments))
        if not self.spreading:
            object.__setattr__(self, "spreading", (False,) * len(self.arguments))

    @property
    def words_text(self) -> str:
        """The command's own words, without redirections or heredoc bodies, for rule matching."""
        return " ".join(self.words)

    @property
    def command_words_text(self) -> str:
        """The command's words with each argument containing whitespace as a placeholder.

        Such an argument is prose such as a PR body or commit message; a shell runs it as a command
        only through eval or a shell -c wrapper, whose script parse judges as separate commands.
        """
        return " ".join(
            RUN_TIME_PLACEHOLDER if re.search(r"\s", argument) else word
            for word, argument in zip(self.words, self.arguments, strict=True)
        )

    @property
    def static_words_text(self) -> str:
        """The command's words with each run-time word as a plain placeholder, for judging the static form."""
        return " ".join(
            RUN_TIME_PLACEHOLDER if dynamic else word for word, dynamic in zip(self.words, self.dynamic, strict=True)
        )

    @property
    def hides_options(self) -> bool:
        """Whether an option can reach the program unseen: quoted or escaped, or inside a spreading expansion."""
        quoted_option = any(
            argument.startswith("-") and word != argument
            for word, argument in zip(self.words, self.arguments, strict=True)
        )
        return quoted_option or any(self.spreading)

    @property
    def has_dynamic_words(self) -> bool:
        return any(self.dynamic)

    @property
    def program_is_dynamic(self) -> bool:
        return bool(self.dynamic) and self.dynamic[0]

    def rebased(self, index: int, head: tuple[str, ...] = (), depth: int | None = None) -> Self:
        """Keep the arguments from one index onward, optionally behind a canonical head or one wrapper deeper."""
        words = (*head, *self.words[index:])
        raw = " ".join((*words, self.trailer)).rstrip()
        wrapper_depth = self.wrapper_depth if depth is None else depth
        return replace(
            self,
            raw=raw,
            arguments=(*head, *self.arguments[index:]),
            wrapper_depth=wrapper_depth,
            words=words,
            dynamic=((False,) * len(head)) + self.dynamic[index:],
            spreading=((False,) * len(head)) + self.spreading[index:],
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
    if any(node.get("Type") not in ALLOWED_NODES for node in records):
        raise UnsupportedSyntax("dynamic or unsupported shell syntax requires explicit review")
    data = source.encode()
    commands: list[Command] = []
    for node in records:
        if node.get("Type") != "CallExpr" or not node.get("Args"):
            continue
        owner = owners.get(id(node), node)
        command = replace(literal_command(node, owner, data), wrapper_depth=depth)
        commands.append(command)
        commands.extend(unwrapped(command))
        innermost = commands[-1]
        if script := shell_script(innermost):
            commands.extend(parse(script, innermost.wrapper_depth + 1))
        elif Path(innermost.arguments[0]).name in SHELLS and (stdin := heredoc_script(owner)):
            commands.extend(parse(stdin, innermost.wrapper_depth + 1))
    return tuple(commands)


def statement_writes(statement: dict, data: bytes) -> tuple[str, ...]:
    redirects = [redirect for redirect in statement.get("Redirs", []) if redirect.get("Word")]
    targets = [literal_word(redirect["Word"], data)[0] for redirect in redirects]
    return tuple(
        target for redirect, target in zip(redirects, targets, strict=True) if writes_file(redirect, target, data)
    )


def is_one_simple_command(source: str) -> bool:
    """Whether the source is one plain call: no list, pipe, background, negation, compound, assignment, or redirect."""
    statements = syntax_tree(source).get("Stmts", [])
    if len(statements) != 1:
        return False
    statement = statements[0]
    flags = ("Background", "Coprocess", "Negated", "Disown", "Redirs")
    command = statement.get("Cmd")
    return (
        not any(statement.get(flag) for flag in flags)
        and isinstance(command, dict)
        and command.get("Type") == "CallExpr"
        and not command.get("Assigns")
    )


def text_outside_single_quotes(source: str) -> str:
    """The source without its single-quoted strings, which no shell expands; $'...' stays, as it decodes escapes."""
    data = source.encode()
    spans = sorted(
        (node["Pos"]["Offset"], node["End"]["Offset"])
        for node in nodes(syntax_tree(source))
        if node.get("Type") == "SglQuoted" and not node.get("Dollar")
    )
    kept, start = [], 0
    for begin, end in spans:
        kept.append(data[start:begin])
        start = max(start, end)
    kept.append(data[start:])
    return b"".join(kept).decode()


def heredoc_script(owner: dict) -> str:
    """Return the static script a shell reads from a heredoc, refusing one the shell computes."""
    bodies = [redirect["Hdoc"] for redirect in owner.get("Redirs", []) if redirect.get("Hdoc")]
    if not bodies:
        return ""
    parts = [part for body in bodies for part in body.get("Parts", [])]
    if any(part.get("Type") != "Lit" for part in parts):
        raise UnsupportedSyntax("a shell heredoc whose text is computed requires explicit review")
    return "".join(part.get("Value", "") for part in parts)


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


def literal_command(node: dict, owner: dict, data: bytes) -> Command:
    """Decode one call expression together with the statement text that owns it."""
    raw = source_text(owner, data).strip()
    if owner.get("Semicolon") and raw.endswith(";"):
        raw = raw[:-1].rstrip()
    if owner.get("Background") and raw.endswith("&"):
        raw = raw[:-1].rstrip()
    redirects = [redirect for redirect in owner.get("Redirs", []) if redirect.get("Word")]
    decoded = [literal_word(word, data) for word in node["Args"]]
    targets = [literal_word(redirect["Word"], data)[0] for redirect in redirects]
    return Command(
        raw,
        tuple(value for value, _ in decoded),
        redirections=tuple(targets),
        words=tuple(source_text(word, data) for word in node["Args"]),
        trailer=" ".join(source_text(redirect, data) for redirect in redirects),
        dynamic=tuple(flag for _, flag in decoded),
        spreading=tuple(spreads(word, data) for word in node["Args"]),
        writes=statement_writes(owner, data),
    )


def writes_file(redirect: dict, target: str, data: bytes) -> bool:
    """Whether a redirection creates or overwrites a file, judged by its operator text, not by parser codes."""
    operator = re.match(r"\d*(&>>|&>|>>|>\||>&|<&|<<<|<>|<|>)", source_text(redirect, data))
    if operator is None:
        return True
    symbol = operator.group(1)
    if symbol in {">&", "<&"}:
        return symbol == ">&" and not (target.isdigit() or target == "-")
    return symbol in {">", ">>", ">|", "&>", "&>>", "<>"}


def source_text(node: dict, source: bytes) -> str:
    """Use byte offsets so non-ASCII input cannot shift command boundaries."""
    return source[node["Pos"]["Offset"] : node["End"]["Offset"]].decode()


def literal_word(word: dict, source: bytes) -> tuple[str, bool]:
    """Decode a word the tree proves static, or return its source text flagged as dynamic.

    Only substitutions that run code (command, process, and arithmetic substitution) and
    dollar-quoted or heredoc forms are refused outright; a glob or a parameter other than the
    home directory is reported to the caller, which decides whether the program can take it.
    """
    dynamic = False
    for part in word_nodes(word):
        if part.get("Type") in QUOTED_PARTS and part.get("Dollar"):
            raise UnsupportedSyntax("dollar-quoted shell words require explicit review")
        if part.get("Type") == "ParamExp":
            dynamic |= not is_home_parameter(part)
        elif part.get("Type") in SUBSTITUTIONS:
            dynamic = True
        elif part.get("Type") not in WORD_PARTS:
            raise UnsupportedSyntax("shell expansions require explicit review")
    parts = word.get("Parts", [])
    for index, part in enumerate(parts):
        if part.get("Type") == "Lit" and not is_literal_text(part.get("Value", ""), first=index == 0):
            dynamic = True
    if dynamic:
        return source_text(word, source), True
    return "".join(literal_part(index, part, source) for index, part in enumerate(parts)), False


def spreads(word: dict, source: bytes) -> bool:
    """Whether a word may become several words, or other words than the decoder sees.

    That is an unquoted expansion, substitution, glob, or brace, a line continuation, which the
    shell removes, or a positional parameter or array expansion even in quotes.
    """
    parts = word.get("Parts", [])
    unquoted = "".join(part.get("Value", "") for part in parts if part.get("Type") == "Lit")
    if any(part.get("Type") in SPLIT_PARTS for part in parts) or GLOB.search(unquoted) or BRACES & set(unquoted):
        return True
    if LINE_CONTINUATION in source_text(word, source):
        return True
    for part in word_nodes(word):
        if part.get("Type") != "ParamExp":
            continue
        name = part.get("Param", {}).get("Value", "")
        index = "".join(inner.get("Value", "") for inner in (part.get("Index") or {}).get("Parts", []))
        if name in SPREADING or name.isdigit() or index in SPREADING:
            return True
    return False


def word_nodes(value: object) -> Iterator[dict]:
    """Walk a word's parts without entering substitutions, whose commands parse judges separately."""
    if isinstance(value, dict):
        yield value
        if value.get("Type") in SUBSTITUTIONS:
            return
        for child in value.values():
            yield from word_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from word_nodes(child)


def is_home_parameter(part: dict) -> bool:
    """Accept a plain $HOME or ${HOME}; any modifier would compute a value the hook cannot predict."""
    name = part.get("Param", {}).get("Value")
    return name == HOME_PARAMETER and not any(part.get(key) for key in PARAMETER_MODIFIERS)


def is_literal_text(value: str, *, first: bool) -> bool:
    """Unquoted globs expand at run time, and so does a leading tilde unless it names the home directory."""
    if GLOB.search(value):
        return False
    if value.startswith("~"):
        return first and (value == "~" or value.startswith("~/"))
    return True


def literal_part(index: int, part: dict, source: bytes) -> str:
    """Decode one word part, substituting the home directory where the tree allowed it."""
    kind = part.get("Type")
    if kind == "ParamExp":
        return home_directory()
    if kind == "SglQuoted":
        return part.get("Value", "")
    if kind == "DblQuoted":
        return "".join(
            home_directory() if inner.get("Type") == "ParamExp" else unquoted('"' + source_text(inner, source) + '"')
            for inner in part.get("Parts", [])
        )
    value = unquoted(source_text(part, source))
    if index == 0 and value.startswith("~"):
        return home_directory() + value[1:]
    return value


def unquoted(text: str) -> str:
    """Decode an unquoted or double-quoted part as the shell does, dropping each line continuation."""
    values = shlex.split(text.replace(LINE_CONTINUATION, ""), posix=True)
    if len(values) != 1:
        raise UnsupportedSyntax("a shell word could not be decoded unambiguously")
    return values[0]


def home_directory() -> str:
    home = os.path.expanduser("~")
    if home == "~":
        raise UnsupportedSyntax("the home directory is unknown, so its expansion requires explicit review")
    return home


def unwrapped(command: Command) -> list[Command]:
    """Peel process wrappers so policy sees the program they eventually run."""
    exposed: list[Command] = []
    while (index := wrapped_index(command.arguments)) is not None:
        appends_input = command.appends_input or Path(command.arguments[0]).name == "xargs"
        command = replace(command.rebased(index, depth=command.wrapper_depth + 1), appends_input=appends_input)
        exposed.append(command)
    return exposed


def wrapped_index(arguments: tuple[str, ...]) -> int | None:
    """Locate the command a process wrapper runs, or None when the call is not a wrapper invocation."""
    name = Path(arguments[0]).name
    if name not in WRAPPERS:
        return None
    _, valued = WRAPPERS[name]
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
        elif (name == "env" and ASSIGNMENT.match(token)) or is_flag(name, token):
            index += 1
        elif token.startswith("-"):
            raise UnsupportedSyntax(f"{name} option requires explicit review: {token}")
        else:
            break
    if name == "timeout":
        index += 1
    return index if index < len(arguments) else None


def is_flag(name: str, token: str) -> bool:
    """Recognize a wrapper's options that carry no separate operand, including attached-value short forms."""
    flags, valued = WRAPPERS[name]
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


def shell_script(command: Command) -> str:
    """Return the literal script that eval or a shell -c invocation runs, or an empty string."""
    arguments = command.arguments
    executable = Path(arguments[0]).name
    if executable == "eval":
        if any(command.dynamic[1:]):
            raise UnsupportedSyntax("eval of a computed script requires explicit review")
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
    if command.dynamic[option + 1]:
        raise UnsupportedSyntax("a shell wrapper running a computed script requires explicit review")
    return arguments[option + 1]
