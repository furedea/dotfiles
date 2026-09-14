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
    return json.loads(subprocess.check_output(["esa", "post", *arguments], text=True))


def post_number(value: object) -> str:
    if isinstance(value, bool) or not str(value).isdigit() or int(str(value)) <= 0:
        raise ValueError("esa: invalid post number")
    return str(value)


def find_post(name: str) -> str:
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
        editor = os.environ.get("EDITOR", "nvim")
        print(f"editor: {editor}", flush=True)
        environment = dict(
            os.environ, ESA_EDIT_POST_NUMBER=number, ESA_EDIT_FILE=str(path), ESA_EDIT_SYNC_FILE=str(synced)
        )
        try:
            subprocess.run([editor, str(path)], env=environment, check=True)
            if path.read_bytes() != synced.read_bytes():
                subprocess.run(
                    ["esa", "post", "update", number, "--body-file", str(path), "--wip", *QUIET], check=True
                )
        except OSError, subprocess.CalledProcessError:
            preserve = path.is_file() and path.read_bytes() != synced.read_bytes()
            raise
        return number
    finally:
        if preserve:
            print(f"esa: edits preserved at {path}", file=sys.stderr)
        else:
            path.unlink(missing_ok=True)
            synced.unlink(missing_ok=True)
            try:
                directory.rmdir()
            except OSError:
                print(f"esa: editor artifacts preserved at {directory}", file=sys.stderr)


def usage(kind: str) -> str:
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
    if kind in {"en", "edit"}:
        return len(arguments) == 1 and bool(arguments[0])
    if kind == "ee":
        return len(arguments) <= 1
    if kind == "eep":
        return not arguments or arguments == [""]
    return not arguments or (len(arguments) == 1 and arguments[0] in {"", "-q", "--quiet", "--no-notice"})


def execute(kind: str, arguments: list[str], previous: str) -> str | None:
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
    try:
        result = execute(kind, rest, previous)
        if result is not None:
            Path(result_file).write_text(result + "\n")
        return 0
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
