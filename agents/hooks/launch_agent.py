#!/usr/bin/env -S python3 -IB
"""Register the target worktree before starting a terminal coding agent."""

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "lib"))

from session_snapshot import repository_root
from session_store import StateError, prune, register


@dataclass(frozen=True, slots=True)
class Launch:
    directory: Path
    arguments: tuple[str, ...]
    resuming: bool = False
    utility: bool = False


@dataclass(frozen=True, slots=True)
class Arguments:
    directory: Path
    values: tuple[str, ...]
    positionals: tuple[str, ...]
    options: tuple[tuple[str, str], ...]


def plan(provider: str, arguments: tuple[str, ...]) -> Launch:
    parsed = parse_arguments(provider, arguments)
    utilities = {
        "login",
        "logout",
        "auth",
        "mcp",
        "plugin",
        "completion",
        "update",
        "doctor",
        "features",
        "help",
        "install",
        "setup-token",
        "archive",
        "unarchive",
        "delete",
        "migrate-rollouts",
        "queue",
        "agents",
    }
    flags = {key for key, _ in parsed.options}
    help_flags = {"--help", "-h", "--version", "-V"} | ({"-v"} if provider == "claude" else set())
    command = next(iter(parsed.positionals), "")
    printing = provider == "claude" and bool(flags & {"-p", "--print"})
    if flags & help_flags or (command in utilities and not printing):
        return Launch(parsed.directory, parsed.values, utility=True)
    if command in {"app", "app-server", "remote-control", "exec-server", "cloud", "attach", "respawn", "bg"}:
        raise StateError("This launcher requires a local terminal session with one worktree")
    unsupported = {
        "--worktree",
        "-w",
        "--add-dir",
        "--bare",
        "--safe-mode",
        "--settings",
        "--setting-sources",
        "--bg",
        "--background",
    }
    for option, value in parsed.options:
        if option in unsupported:
            raise StateError(
                f"{option} can change the registered worktree or hooks; start in the target worktree using persisted settings"
            )
        if option == "--disable" and {"hooks", "codex_hooks"} & set(value.split(",")):
            raise StateError("Mandatory verification hooks cannot be disabled by launcher arguments")
        if provider == "codex" and option in {"-c", "--config"}:
            check_hook_configuration(value)
    resuming = command in {"resume", "fork"} or parsed.positionals[:2] in {("exec", "resume"), ("e", "resume")}
    resuming |= provider == "claude" and bool(flags & {"--resume", "-r", "--continue", "-c", "--fork-session"})
    prefix = ("-c", "features.hooks=true") if provider == "codex" else ("--settings", '{"disableAllHooks":false}')
    return Launch(parsed.directory, (*prefix, *parsed.values), resuming=resuming)


def parse_arguments(provider: str, arguments: tuple[str, ...]) -> Arguments:
    value_flags = {
        "--config",
        "-C",
        "--cd",
        "-m",
        "--model",
        "--profile",
        "--enable",
        "--disable",
        "-s",
        "--sandbox",
        "-a",
        "--ask-for-approval",
        "--session-id",
        "--permission-mode",
        "--settings",
        "--setting-sources",
        "-i",
        "--image",
        "-o",
        "--output-last-message",
        "--output-format",
        "--input-format",
        "--system-prompt",
        "--append-system-prompt",
    } | ({"-c", "-p"} if provider == "codex" else set())
    directory = Path.cwd()
    values: list[str] = []
    positionals: list[str] = []
    options: list[tuple[str, str]] = []
    iterator = iter(arguments)
    for argument in iterator:
        if argument == "--":
            remaining = tuple(iterator)
            values.extend((argument, *remaining))
            positionals.extend(remaining)
            break
        if not argument.startswith("-"):
            values.append(argument)
            positionals.append(argument)
            continue
        option, separator, value = argument.partition("=")
        if provider == "codex" and argument.startswith("-C") and argument != "-C":
            option, separator, value = "-C", "=", argument[2:].removeprefix("=")
        if option in value_flags and not separator:
            value = next(iterator, "")
            if not value:
                raise StateError(f"Missing value for {option}")
        options.append((option, value))
        if provider == "codex" and option in {"-C", "--cd"}:
            directory = Path(value).expanduser().resolve()
            values.extend(("--cd", str(directory)))
        elif option in value_flags and not separator:
            values.extend((option, value))
        else:
            values.append(argument)
    return Arguments(directory, tuple(values), tuple(positionals), tuple(options))


def check_hook_configuration(value: str) -> None:
    try:
        configuration = tomllib.loads(value)
    except tomllib.TOMLDecodeError:
        return  # Codex also accepts literal strings for unrelated settings.
    features = configuration.get("features", {})
    if isinstance(features, dict) and any(features.get(key) is False for key in ("hooks", "codex_hooks")):
        raise StateError("Mandatory verification hooks cannot be disabled by launcher arguments")
    if configuration.get("allow_managed_hooks_only"):
        raise StateError("Mandatory verification hooks cannot be excluded by launcher arguments")


def launch(provider: str, executable: str, arguments: tuple[str, ...]) -> int:
    options = plan(provider, arguments)
    if options.utility:
        return subprocess.call([executable, *options.arguments])
    root = repository_root(options.directory)
    prune()
    run = register(root, provider, resuming=options.resuming)
    environment = dict(os.environ, AGENT_VERIFICATION_RUN=str(run.directory))
    with run.lease():
        try:
            with subprocess.Popen([executable, *options.arguments], cwd=root, env=environment) as process:
                status = wait_for_provider(process)
        finally:
            with run.lock():
                run.end()
    prune()
    return status if status >= 0 else 128 - status


def wait_for_provider(process: subprocess.Popen) -> int:
    def forward(signum: int, _frame: object) -> None:
        process.send_signal(signum)

    previous = {signum: signal.signal(signum, forward) for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        return process.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main() -> int:
    arguments = sys.argv[1:]
    if len(arguments) < 2 or arguments[0] not in {"codex", "claude"}:
        print("Usage: launch_agent.py codex|claude /absolute/provider/binary [arguments ...]", file=sys.stderr)
        return 0 if arguments in (["-h"], ["--help"]) else 1
    try:
        return launch(arguments[0], arguments[1], tuple(arguments[2:]))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Agent launch refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
