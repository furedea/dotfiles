"""Verification must leave the coding agent's controlling terminal untouched."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

from tests.runtime import REPO_ROOT


pty = pytest.importorskip("pty", reason="Requires POSIX terminal job control")


@pytest.mark.integration
def test_verification_preserves_terminal_foreground_group(tmp_path: Path) -> None:
    zsh = shutil.which("zsh")
    timeout = shutil.which("timeout") or shutil.which("gtimeout")
    managed_timeout = Path.home() / ".config/agent-harness/bin/timeout"
    if timeout is None and os.access(managed_timeout, os.X_OK):
        timeout = str(managed_timeout)
    if zsh is None or timeout is None:
        pytest.skip("Requires Zsh and GNU timeout")

    hook = tmp_path / "hook.py"
    hook.write_text(
        textwrap.dedent(
            """
            import json
            from pathlib import Path
            import runpy
            import sys
            import time

            gate = runpy.run_path(sys.argv[1])
            invocation = gate["verification_selection"].Invocation(
                "bats", "terminal fixture", (sys.argv[2], "-dfi", "-c", "print '1..1'; print 'ok 1 fixture'")
            )
            report = gate["Report"](Path.cwd(), time.monotonic())
            gate["verify"](invocation, report)
            print(json.dumps(report.notification()))
            """
        )
    )
    terminal = tmp_path / "terminal.py"
    terminal.write_text(
        textwrap.dedent(
            """
            import fcntl
            import json
            import os
            import subprocess
            import sys
            import termios

            fd = int(sys.argv[1])
            fcntl.ioctl(fd, termios.TIOCSCTTY, 0)
            before = os.tcgetpgrp(fd)
            hook = subprocess.run(
                [sys.executable, "-I", "-B", *sys.argv[2:]],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                process_group=0, timeout=10, check=True,
            )
            print(json.dumps({
                "before": before, "after": os.tcgetpgrp(fd),
                "notification": json.loads(hook.stdout), "stderr": hook.stderr,
            }))
            """
        )
    )
    master, slave = pty.openpty()
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                str(terminal),
                str(slave),
                str(hook),
                str(REPO_ROOT / "agents/hooks/run_verification.py"),
                zsh,
            ],
            cwd=tmp_path,
            env=os.environ
            | {
                "RUN_RELATED_TESTS_TIMEOUT_BIN": timeout,
                "RUN_RELATED_TESTS_TIMEOUT_SECONDS": "3",
                "XDG_STATE_HOME": str(tmp_path / "state"),
            },
            pass_fds=(slave,),
            start_new_session=True,
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
    finally:
        os.close(master)
        os.close(slave)

    observed = json.loads(result.stdout)
    assert observed["stderr"] == ""
    assert observed["notification"]["systemMessage"].startswith("Verification passed")
    assert observed["after"] == observed["before"], "Verification stole the agent's terminal input"
