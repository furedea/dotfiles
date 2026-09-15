"""Exercise the Nix-packaged Hermes gateway in an isolated macOS profile."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.runtime import REPO_ROOT


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform != "darwin", reason="requires the macOS Nix-built Hermes package"),
]
PACKAGE_EXPRESSION = """
{ flakeRef, output }:
let
  flake = builtins.getFlake flakeRef;
  packages = flake.homeConfigurations.kaito.config.home.packages;
  hermes = builtins.head (
    builtins.filter (package: (package.pname or package.name) == "hermes-agent") packages
  );
in if output == "package" then hermes else builtins.getAttr output hermes
"""


@dataclass(frozen=True, slots=True)
class HermesRuntime:
    python: Path
    plugins: Path


@pytest.fixture(scope="module")
def hermes_runtime() -> HermesRuntime:
    package = build_hermes_output("package")
    venv = build_hermes_output("hermesVenv")
    return HermesRuntime(venv / "bin/python3", package / "share/hermes-agent/plugins")


def test_slack_gateway_dependencies_are_available(hermes_runtime: HermesRuntime, tmp_path: Path) -> None:
    assert run_probe(hermes_runtime, tmp_path, "slack_available") is True


def test_launchd_does_not_persist_credential_environment(hermes_runtime: HermesRuntime, tmp_path: Path) -> None:
    assert run_probe(hermes_runtime, tmp_path, "persisted_credential_names") == []


def test_launchd_discovers_the_bundled_slack_plugin(hermes_runtime: HermesRuntime, tmp_path: Path) -> None:
    result = run_probe(hermes_runtime, tmp_path, "bundled_plugin")
    assert isinstance(result, dict)
    assert result["returncode"] == 0, result["stderr"]
    assert "slack-platform" in result["stdout"], result


def run_probe(runtime: HermesRuntime, home: Path, operation: str) -> object:
    result = subprocess.run(
        [str(runtime.python), "-I", "-B", str(REPO_ROOT / "tests/hermes/gateway_probe.py"), operation],
        cwd=home,
        env={
            "HOME": str(home),
            "HERMES_HOME": str(home / ".hermes"),
            "HERMES_BUNDLED_PLUGINS": str(runtime.plugins),
            "PATH": os.environ["PATH"],
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def build_hermes_output(output: str) -> Path:
    result = subprocess.run(
        [
            "nix",
            "build",
            "--no-link",
            "--no-write-lock-file",
            "--print-out-paths",
            "--impure",
            "--expr",
            PACKAGE_EXPRESSION,
            "--argstr",
            "flakeRef",
            os.environ.get("DOTFILES_TEST_FLAKE", f"git+file://{REPO_ROOT}"),
            "--argstr",
            "output",
            output,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return Path(result.stdout.strip())
