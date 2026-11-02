#!/usr/bin/env -S python3 -IB
"""Apply the linked Herdr config to every running session; never fail Home Manager activation."""

import json
import subprocess
import sys


TIMEOUT_SECONDS = 15


class HerdrCommandError(Exception):
    """A Herdr command could not run or did not return a JSON object."""


def main(arguments: list[str]) -> int:
    """Reload each running session's config, reporting problems without a failing exit status."""
    if len(arguments) != 1 or arguments[0] in {"-h", "--help"}:
        print("Usage: config_reload.py <HERDR_EXECUTABLE>", file=sys.stderr)
        return 0
    executable = arguments[0]
    try:
        sessions = running_sessions(executable)
    except HerdrCommandError as error:
        print(f"Skipping Herdr config reload: session list unavailable ({error}).")
        return 0
    if not sessions:
        print("Skipping Herdr config reload: no Herdr session is running.")
    for session in sessions:
        reload_session(executable, session)
    return 0


def running_sessions(executable: str) -> list[str]:
    """Name every session whose server is running; each has its own socket and config state."""
    listed = query(executable, "session", "list", "--json").get("sessions")
    entries = listed if isinstance(listed, list) else []
    return [
        entry["name"]
        for entry in entries
        if isinstance(entry, dict) and entry.get("running") is True and isinstance(entry.get("name"), str)
    ]


def reload_session(executable: str, session: str) -> None:
    """Reload one session's server when it is running and compatible with this client."""
    try:
        server = query(executable, "--session", session, "status", "server", "--json")
    except HerdrCommandError as error:
        print(f"Skipping Herdr config reload for session {session!r}: status unavailable ({error}).")
        return
    if server.get("running") is not True:
        print(f"Skipping Herdr config reload for session {session!r}: server is not running.")
        return
    if server.get("compatible") is not True:
        print(f"Skipping Herdr config reload for session {session!r}: server is incompatible; restart it.")
        return
    try:
        result = query(executable, "--session", session, "server", "reload-config").get("result")
    except HerdrCommandError as error:
        warn(
            f"Herdr config reload failed for session {session!r} ({error}); "
            f"run `herdr --session {session} server reload-config` manually."
        )
        return
    report(session, result if isinstance(result, dict) else {})


def query(executable: str, *arguments: str) -> dict:
    """Run a Herdr command and parse its JSON object output."""
    try:
        completed = subprocess.run(
            [executable, *arguments], capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise HerdrCommandError(str(error)) from error
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise HerdrCommandError(f"exit status {completed.returncode}: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise HerdrCommandError(f"unreadable output: {completed.stdout.strip()!r}") from error
    if not isinstance(payload, dict):
        raise HerdrCommandError(f"unexpected output: {completed.stdout.strip()!r}")
    return payload


def report(session: str, result: dict) -> None:
    """Warn about diagnostics or an unapplied reload so a broken config is noticed."""
    status = result.get("status")
    diagnostics = result.get("diagnostics") or []
    if status == "applied" and not diagnostics:
        print(f"Reloaded Herdr config in session {session!r}.")
        return
    warn(f"Herdr config reload for session {session!r} finished with status {status!r}.")
    for diagnostic in diagnostics:
        warn(f"  {json.dumps(diagnostic, ensure_ascii=False)}")


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
