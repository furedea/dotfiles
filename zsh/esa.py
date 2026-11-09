"""Edit esa posts through the existing CLI; the parent Zsh owns session state."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PERSONAL = "Members/k-shigyo"
# Preserve the exact remote esa post name.
# autocorrect-disable space-word
MINUTES = "議事録/2026年度配属/shigyo"
# autocorrect-enable
QUIET = ["--message", "[skip notice]"]


def esa_json(arguments: list[str]) -> dict:
    """Run `esa post` with the given arguments and parse its JSON output.

    Raises:
        subprocess.CalledProcessError: The esa command exited with a non-zero status.
    """
    return json.loads(subprocess.check_output(["esa", "post", *arguments], text=True))


def post_number(value: object) -> str:
    """Validate an esa post number.

    Returns:
        The number as a string of digits.

    Raises:
        ValueError: The value is not a positive integer.
    """
    if isinstance(value, bool) or not str(value).isdigit() or int(str(value)) <= 0:
        raise ValueError("esa: invalid post number")
    return str(value)


def find_post(name: str) -> str:
    """Look up a post by its full name.

    Args:
        name: Category and title joined by "/".

    Returns:
        The post number.

    Raises:
        ValueError: No post or more than one post has that full name.
    """
    result = esa_json(
        [
            "search",
            "full_name:" + json.dumps(name, ensure_ascii=False),
            "--per-page",
            "100",
            "--json",
            "number,name,category,full_name",
        ]
    )
    matches = [post for post in result["posts"] if post["category"] + "/" + post["name"] == name]
    if len(matches) != 1:
        raise ValueError("esa: post not found uniquely")
    return post_number(matches[0]["number"])


def select_post() -> str:
    """Let the user pick one of their recently updated personal posts with fzf.

    Returns:
        The chosen post number, or an empty string when nothing was chosen.
    """
    result = esa_json(
        ["search", f'in:"{PERSONAL}" sort:updated-desc', "--per-page", "100", "--json", "number,full_name"]
    )
    rows = "".join(f"{post_number(post['number'])}\t{post['full_name']}\n" for post in result["posts"])
    selection = subprocess.run(
        ["fzf", "--delimiter=\t", "--with-nth=2..", "--prompt=esa > "],
        input=rows,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    return post_number(selection.partition("\t")[0]) if selection else ""


def edit(number: str) -> str:
    """Edit a post body in a temporary file and upload it when it changed.

    Unsaved edits are kept on disk when the editor or the upload fails.

    Args:
        number: The post number.

    Returns:
        The validated post number.
    """
    number = post_number(number)
    directory = Path(tempfile.mkdtemp(prefix="esa-edit."))
    path, synced = directory / "post.md", directory / "synced.md"
    preserve = False
    try:
        body = esa_json(["view", number, "--json", "body_md"])["body_md"]
        if not isinstance(body, str):
            raise ValueError("esa: invalid post body")
        path.write_text(body + "\n")
        synced.write_bytes(path.read_bytes())
        try:
            edit_and_save(number, path, synced)
        except OSError, subprocess.CalledProcessError:
            preserve = path.is_file() and path.read_bytes() != synced.read_bytes()
            raise
        return number
    finally:
        if preserve:
            print(f"esa: edits preserved at {path}", file=sys.stderr)
        else:
            remove_edit_files(directory, path, synced)


def edit_and_save(number: str, path: Path, synced: Path) -> None:
    """Open the editor on the post file and update the post as WIP if the content differs from the synced copy.

    Args:
        number: The post number.
        path: The file the editor opens.
        synced: A copy of the content last known to be on esa.
    """
    editor = os.environ.get("EDITOR", "nvim")
    print(f"editor: {editor}", flush=True)
    environment = dict(
        os.environ, ESA_EDIT_POST_NUMBER=number, ESA_EDIT_FILE=str(path), ESA_EDIT_SYNC_FILE=str(synced)
    )
    subprocess.run([editor, str(path)], env=environment, check=True)
    if path.read_bytes() != synced.read_bytes():
        subprocess.run(["esa", "post", "update", number, "--body-file", str(path), "--wip", *QUIET], check=True)


def remove_edit_files(directory: Path, path: Path, synced: Path) -> None:
    """Delete the temporary edit files and their directory, keeping the directory if it holds other files."""
    path.unlink(missing_ok=True)
    synced.unlink(missing_ok=True)
    try:
        directory.rmdir()
    except OSError:
        print(f"esa: editor artifacts preserved at {directory}", file=sys.stderr)


def usage(kind: str) -> str:
    """Build the help text for one command kind (en, ee, eep, es or edit)."""
    arguments = {"en": " <title>", "ee": " [title]", "eep": "", "es": " [-q|--quiet]", "edit": " <number>"}
    descriptions = {
        "en": f"Create a WIP post under {PERSONAL} and edit it with $EDITOR.",
        "ee": f"Open a post under {PERSONAL} with $EDITOR; without a title, choose with fzf.",
        "eep": f"Open {MINUTES} with $EDITOR.",
        "es": "Ship the last post opened by en, ee, or eep.",
        "edit": "Open a numbered post with $EDITOR.",
    }
    options = "  -q, --quiet, --no-notice  Ship without notification\n" if kind == "es" else ""
    return f"Usage: {kind}{arguments[kind]}\n\n{descriptions[kind]}\n\nOptions:\n{options}  -h, --help  Show this help"


def valid_arguments(kind: str, arguments: list[str]) -> bool:
    """Report whether the arguments fit the command kind's usage."""
    if kind in {"en", "edit"}:
        return len(arguments) == 1 and bool(arguments[0])
    if kind == "ee":
        return len(arguments) <= 1
    if kind == "eep":
        return not arguments or arguments == [""]
    return not arguments or (len(arguments) == 1 and arguments[0] in {"", "-q", "--quiet", "--no-notice"})


def execute(kind: str, arguments: list[str], previous: str) -> str | None:
    """Run one command kind: create, open or select a post and edit it, or ship the previous post.

    Args:
        kind: The command kind.
        arguments: Validated arguments for the kind.
        previous: Number of the last edited post, empty if none.

    Returns:
        The edited post number, an empty string after shipping, or None when no post was selected.

    Raises:
        ValueError: Shipping was requested without a previous post.
    """
    if kind == "es":
        if not previous:
            raise ValueError("es: no post to ship (edit something first)")
        options = QUIET if arguments and arguments[0] else []
        subprocess.run(["esa", "post", "update", post_number(previous), "--ship", *options], check=True)
        return ""
    if kind == "en":
        number = post_number(
            esa_json(["create", f"{PERSONAL}/{arguments[0]}", "--wip", *QUIET, "--json", "number"])["number"]
        )
    elif kind == "edit":
        number = post_number(arguments[0])
    elif kind == "eep":
        number = find_post(MINUTES)
    else:
        number = find_post(f"{PERSONAL}/{arguments[0]}") if arguments and arguments[0] else select_post()
    return edit(number) if number else None


def main(arguments: list[str]) -> int:
    """Run the command and convert expected failures to an exit status.

    Returns:
        0 on success, the failing command's status, 1 for invalid input, or 130 on interrupt.
    """
    try:
        return run(arguments)
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def run(arguments: list[str]) -> int:
    """Parse the Zsh wrapper's arguments, execute the command and write the resulting post number to the result file.

    Args:
        arguments: The result file, the previous post number, the command kind and its arguments.

    Returns:
        0 on success, 1 on a usage error.
    """
    if len(arguments) < 3 or arguments[2] not in {"en", "ee", "eep", "es", "edit"}:
        print("Usage: esa.py RESULT_FILE PREVIOUS_POST <en|ee|eep|es|edit> [arguments]", file=sys.stderr)
        return 1
    result_file, previous, kind, *rest = arguments
    if rest in (["-h"], ["--help"]):
        print(usage(kind))
        return 0
    if not valid_arguments(kind, rest):
        print(usage(kind), file=sys.stderr)
        return 1
    result = execute(kind, rest, previous)
    if result is not None:
        Path(result_file).write_text(result + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
