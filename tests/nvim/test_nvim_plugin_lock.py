"""Neovim plugin revisions stay reproducible without bootstrapping lazy.nvim."""

import json
import re
import subprocess

from tests.runtime import REPO_ROOT


def test_neovim_does_not_bootstrap_lazy_from_github() -> None:
    source = (REPO_ROOT / "nvim/init.lua").read_text()
    assert "https://github.com/folke/lazy.nvim.git" not in source


def test_plugin_lock_is_not_ignored_by_git() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "nvim/lazy-lock.json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr


def test_plugin_lock_pins_revisions_except_the_nix_managed_loader() -> None:
    plugins = json.loads((REPO_ROOT / "nvim/lazy-lock.json").read_text())
    assert isinstance(plugins, dict) and plugins
    assert "lazy.nvim" not in plugins
    for name, plugin in plugins.items():
        assert re.fullmatch(r"[0-9a-f]{40}", plugin["commit"]), name
