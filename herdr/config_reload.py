#!/usr/bin/env -S python3 -IB
"""Apply the linked Herdr config to a running server; never fail Home Manager activation."""

import json
import subprocess
import sys


TIMEOUT_SECONDS = 15


class HerdrCommandError(Exception):
    """A Herdr command could not run or did not return a JSON object."""


def main(arguments: list[str]) -> int:
    """Reload the running server's config, reporting problems without a failing exit status."""
    if len(arguments) != 1 or arguments[0] in {"-h", "--help"}:
        print("Usage: config_reload.py <HERDR_EXECUTABLE>", file=sys.stderr)
        return 0
    executable = arguments[0]
    try:
        server = query(executable, "status", "server", "--json")
    except HerdrCommandError as error:
        print(f"Skipping Herdr config reload: server status unavailable ({error}).")
        return 0
    if server.get("running") is not True:
        print("Skipping Herdr config reload: no Herdr server is running.")
        return 0
    if server.get("compatible") is not True:
        print("Skipping Herdr config reload: the running Herdr server is incompatible; restart it.")
        return 0
    try:
        result = query(executable, "server", "reload-config").get("result")
    except HerdrCommandError as error:
        warn(f"Herdr config reload failed ({error}); run `herdr server reload-config` manually.")
        return 0
    report(result if isinstance(result, dict) else {})
    return 0


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


def report(result: dict) -> None:
    """Warn about diagnostics or an unapplied reload so a broken config is noticed."""
    status = result.get("status")
    diagnostics = result.get("diagnostics") or []
    if status == "applied" and not diagnostics:
        print("Reloaded Herdr config in the running server.")
        return
    warn(f"Herdr config reload finished with status {status!r}.")
    for diagnostic in diagnostics:
        warn(f"  {json.dumps(diagnostic, ensure_ascii=False)}")


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
