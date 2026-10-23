"""Git wrappers delegate without re-entering PATH-based platform shims."""

import os
from pathlib import Path
import shlex
import subprocess

import pytest

from tests.runtime import real_git


@pytest.mark.parametrize("shim_first", [True, False])
def test_git_wrapper_bypasses_path_lookup_in_platform_shims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shim_first: bool
) -> None:
    exec_path = subprocess.run(["git", "--exec-path"], check=True, capture_output=True, text=True).stdout.strip()
    binary = Path(exec_path) / "git"
    expected = subprocess.run([str(binary), "--version"], check=True, capture_output=True, text=True).stdout
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "git").write_text(
        '#!/bin/sh\nif [ "$1" = --exec-path ]; then\n'
        f"printf '%s\\n' {shlex.quote(exec_path)}\n"
        'else\nexec git "$@"\nfi\n'
    )
    (shim / "git").chmod(0o755)
    directories = [str(shim), str(binary.parent)]
    if not shim_first:
        directories.reverse()
    monkeypatch.setenv("PATH", os.pathsep.join(directories))
    executable = real_git()
    wrapper = tmp_path / "wrapper"
    wrapper.mkdir()
    (wrapper / "git").write_text(f'#!/bin/sh\nexec {shlex.quote(executable)} "$@"\n')
    (wrapper / "git").chmod(0o755)
    monkeypatch.setenv("PATH", str(wrapper) + os.pathsep + os.environ["PATH"])

    result = subprocess.run(["git", "--version"], check=True, capture_output=True, text=True, timeout=30)

    assert result.stdout == expected
