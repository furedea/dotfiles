"""Translate Codex hook payloads at the boundary to shared hook implementations."""

import json
import os
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve()
COMMON = SCRIPT.parents[2] / (".claude/hooks" if SCRIPT.parent.parent.name == ".codex" else "hooks")
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(COMMON / "lib"))

import audit_events
import patch_input
import secret_paths
import shell_syntax

EXTENSIONS = {
    ".py": "py",
    ".sh": "sh",
    ".js": "js",
    ".ts": "js",
    ".jsx": "js",
    ".tsx": "js",
    ".rs": "rs",
    ".nix": "nix",
    ".md": "md",
    ".markdown": "md",
    ".json": "json_toml",
    ".toml": "json_toml",
    ".yml": "gha",
    ".yaml": "gha",
    ".txt": "txt",
    ".lua": "lua",
    ".tex": "tex",
    ".bib": "tex",
    ".cls": "tex",
    ".sty": "tex",
}


def shared_directory() -> Path:
    return Path(os.environ.get("AGENT_HARNESS_ROOT", str(Path.home()))) / ".claude/hooks"


def translated(payload: dict, tool: str, values: dict) -> dict:
    return {"tool_name": tool, "tool_input": values, "session_id": payload.get("session_id") or ""}


def invoke(path: Path, payload: dict, arguments: tuple[str, ...] = ()) -> int:
    if not os.access(path, os.X_OK):
        raise ValueError(f"shared hook is not executable: {path}")
    return subprocess.run([str(path), *arguments], input=json.dumps(payload), text=True, check=False).returncode


def plain_context(output: str) -> str:
    try:
        value = json.loads(output)
        return value.get("hookSpecificOutput", {}).get("additionalContext") or output
    except ValueError, AttributeError:
        return output


def lint(payload: dict) -> int:
    for name in patch_input.paths((payload.get("tool_input") or {}).get("command") or ""):
        path = Path(name)
        kind = EXTENSIONS.get(path.suffix)
        if not kind or not path.is_file():
            continue
        hook = shared_directory() / f"lint_format_{kind}.sh"
        try:
            result = subprocess.run(
                [str(hook)],
                input=json.dumps(translated(payload, "Edit", {"file_path": name})),
                text=True,
                capture_output=True,
                check=False,
            )
            output = result.stdout.rstrip()
            if result.returncode and result.stderr:
                output += ("\n" if output else "") + result.stderr.rstrip()
        except OSError as error:
            output = str(error)
        if output:
            print(plain_context(output))
    return 0


def harness(payload: dict) -> int:
    hook = shared_directory() / "guard_harness_files.sh"
    if not os.access(hook, os.X_OK):
        raise ValueError(f"harness boundary hook is not executable: {hook}")
    for name in patch_input.paths((payload.get("tool_input") or {}).get("command") or ""):
        absolute = name if name.startswith(("/", "~/")) else str(Path.cwd() / name)
        if status := invoke(hook, translated(payload, "apply_patch", {"file_path": absolute})):
            return status
    return 0


def check_paths(mode: str, payload: dict) -> int:
    policy = Path(
        os.environ.get("AGENT_SECRET_PATH_POLICY", str(shared_directory() / "rules/secret_path_policy.json"))
    )
    rules = secret_paths.load(policy)
    values = payload.get("tool_input") or {}
    command = values.get("command") or values.get("cmd") or ""
    if mode == "command":
        try:
            commands = shell_syntax.parse(command)
        except shell_syntax.UnsupportedSyntax as error:
            raise ValueError(f"{error}\n\nCommand: {command}") from error
        candidates = [word for item in commands for word in (*item.arguments, *item.redirections)]
        candidates += [word.partition("=")[2] for word in candidates if "=" in word]
    else:
        candidates = [values.get("file_path") or values.get("path") or "", *patch_input.paths(command)]
    for value in candidates:
        if rule := secret_paths.blocked_rule(value, rules):
            audit_events.blocked(
                "Bash" if mode == "command" else "apply_patch",
                command if mode == "command" else value,
                f"{rule['reason']}: {value}",
                "adapt_guard_secret_paths.sh",
                payload.get("session_id") or "",
            )
            raise ValueError(
                f"secret path policy matched.\n\nPath: {value}\nPattern: {rule['pattern']}\n\nWhy:\n  {rule['reason']}"
            )
    return 0


def dispatch(kind: str, arguments: list[str], payload: dict) -> int:
    values = payload.get("tool_input") or {}
    if kind == "shell":
        return invoke(
            Path(arguments[0]),
            translated(payload, "Bash", {"command": values.get("command") or values.get("cmd") or ""}),
        )
    if kind == "lint":
        return lint(payload)
    if kind == "harness":
        return harness(payload)
    if kind == "paths":
        return check_paths(arguments[0], payload)
    scanner = shared_directory() / "guard_secret_content.sh"
    if arguments[0] == "prompt":
        return invoke(scanner, payload, ("prompt",))
    return invoke(
        scanner,
        translated(payload, "Edit", {"content": patch_input.added_text(values.get("command") or "")}),
        ("write",),
    )


def main(arguments: list[str]) -> int:
    kind = arguments[0] if arguments else ""
    rest = arguments[1:]
    valid = (
        (kind in {"lint", "harness"} and not rest)
        or (kind == "shell" and len(rest) == 1)
        or (
            kind in {"paths", "content"}
            and len(rest) == 1
            and rest[0] in ({"command", "patch"} if kind == "paths" else {"prompt", "apply-patch"})
        )
    )
    if not valid or any(value in {"-h", "--help"} for value in rest):
        print(
            "Usage: adapters.py <shell HOOK_PATH|lint|harness|paths command/patch|content prompt/apply-patch>",
            file=sys.stderr,
        )
        return 1
    try:
        payload = json.load(sys.stdin)
        if payload.get("cwd"):
            os.chdir(payload["cwd"])
        return dispatch(kind, rest, payload)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
