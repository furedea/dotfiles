"""Observe Hermes through its own Nix-built interpreter, without requiring pytest there."""

import importlib
import json
import os
import plistlib
import subprocess
import sys


def slack_available() -> bool:
    return importlib.import_module("plugins.platforms.slack.adapter").SLACK_AVAILABLE


def persisted_credential_names() -> list[str]:
    names = {"OPENAI_API_KEY", "SLACK_BOT_TOKEN"}
    for name in names:
        os.environ[name] = "credential-sentinel"
    return sorted(names & launchd_environment().keys())


def bundled_plugin() -> dict:
    environment = os.environ.copy()
    environment.pop("HERMES_BUNDLED_PLUGINS", None)
    environment.update(launchd_environment())
    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "plugins", "list", "--plain"],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=30,
    )
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def launchd_environment() -> dict[str, str]:
    gateway = importlib.import_module("hermes_cli.gateway")
    return plistlib.loads(gateway.generate_launchd_plist().encode())["EnvironmentVariables"]


if __name__ == "__main__":
    probes = {
        "slack_available": slack_available,
        "persisted_credential_names": persisted_credential_names,
        "bundled_plugin": bundled_plugin,
    }
    print(json.dumps(probes[sys.argv[1]]()))
