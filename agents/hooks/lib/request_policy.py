"""Judge curl and wget on their decoded arguments: only requests that stay on this machine pass.

A remote request can send local data however its options read, through another scheme, a default
configuration file, or input the guard cannot see, so every remote request asks.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import re


REMOTE_REASON = (
    "Needs review: remote curl/wget can send local data. Read web pages with the web-fetch tool, "
    "or use gh api / nix store prefetch-file for exact values and files."
)
LOCAL_URL = re.compile(r"https?://(localhost|127\.0\.0\.1)(:[0-9]+)?([/?#].*)?")
ValueRule = Callable[[str], bool]


def any_value(_: str) -> bool:
    return True


def header_value(value: str) -> bool:
    """A header given inline; curl reads one starting with @ from a file or standard input."""
    return not value.startswith("@")


@dataclass(frozen=True, slots=True)
class Options:
    """The options one program may use toward this machine: flags, and options whose value a rule judges.

    Each program has its own table, since a letter can be a flag to one and take a value in the other.

    `attached_long` allows `--name=value`, which wget accepts and curl does not.
    """

    flags: frozenset[str]
    valued: dict[str, ValueRule]
    attached_long: bool


CURL = Options(
    flags=frozenset(
        {
            *(f"-{letter}" for letter in "#0146IJLNORSZfgiklsv"),
            "--compressed",
            "--create-dirs",
            "--fail",
            "--fail-with-body",
            "--get",
            "--globoff",
            "--head",
            "--http1.1",
            "--http2",
            "--include",
            "--insecure",
            "--ipv4",
            "--ipv6",
            "--location",
            "--no-buffer",
            "--no-progress-meter",
            "--progress-bar",
            "--remote-header-name",
            "--remote-name",
            "--remote-name-all",
            "--retry-all-errors",
            "--retry-connrefused",
            "--show-error",
            "--silent",
            "--verbose",
        }
    ),
    valued={
        **dict.fromkeys(("-H", "--header"), header_value),
        # Toward this machine, curl may also choose a method and send data.
        **dict.fromkeys(("-X", "--request", "-d", "--data", "--data-raw", "--data-binary", "--json"), any_value),
        **dict.fromkeys(
            (
                "-A",
                "-D",
                "-e",
                "-m",
                "-o",
                "-r",
                "-w",
                "-z",
                "--connect-timeout",
                "--dump-header",
                "--limit-rate",
                "--max-filesize",
                "--max-time",
                "--output",
                "--output-dir",
                "--range",
                "--referer",
                "--retry",
                "--retry-delay",
                "--retry-max-time",
                "--user-agent",
                "--write-out",
            ),
            any_value,
        ),
    },
    attached_long=False,
)
WGET = Options(
    flags=frozenset(
        {
            *(f"-{letter}" for letter in "NSckqv"),
            "-nc",
            "-nd",
            "-nH",
            "-nv",
            "--continue",
            "--no-check-certificate",
            "--no-verbose",
            "--quiet",
            "--server-response",
            "--spider",
            "--timestamping",
        }
    ),
    valued={
        **dict.fromkeys(("--header",), header_value),
        **dict.fromkeys(
            (
                "-O",
                "-P",
                "-T",
                "-U",
                "-t",
                "--directory-prefix",
                "--output-document",
                "--timeout",
                "--tries",
                "--user-agent",
            ),
            any_value,
        ),
    },
    attached_long=True,
)
PROGRAMS: dict[str, Options] = {"curl": CURL, "wget": WGET}


def is_local(arguments: tuple[str, ...]) -> bool:
    """Whether a literal curl or wget call talks only to an HTTP server on this machine, with listed options."""
    urls = operands(arguments[1:], PROGRAMS[arguments[0]])
    return bool(urls) and all(LOCAL_URL.fullmatch(url) for url in urls)


def operands(arguments: tuple[str, ...], options: Options) -> tuple[str, ...] | None:
    """The URLs when every option is listed with an acceptable value, else None."""
    urls: list[str] = []
    words = iter(arguments)
    for word in words:
        if word == "--":
            urls.extend(words)
        elif word == "-" or not word.startswith("-"):
            urls.append(word)
        elif not accepts(word, words, options):
            return None
    return tuple(urls)


def accepts(word: str, words: Iterator[str], options: Options) -> bool:
    """Consume one option, and its value if it takes one, reporting whether it is allowed."""
    if word in options.flags:
        return True
    if word.startswith("--"):
        name, separator, value = word.partition("=")
        if separator:
            return options.attached_long and name in options.valued and options.valued[name](value)
        value = next(words, None)
        return word in options.valued and value is not None and options.valued[word](value)
    return accepts_cluster(word, words, options)


def accepts_cluster(word: str, words: Iterator[str], options: Options) -> bool:
    """Read combined short options such as -sSo, where the last letter may take the next word as its value."""
    for index, letter in enumerate(word[1:], 1):
        option = f"-{letter}"
        if option in options.flags:
            continue
        rule = options.valued.get(option)
        if rule is None:
            return False
        value = word[index + 1 :] or next(words, None)
        return value is not None and rule(value)
    return True
