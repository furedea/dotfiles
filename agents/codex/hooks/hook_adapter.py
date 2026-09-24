#!/usr/bin/env -S python3 -IB
"""Translate Codex hook payloads at the boundary to shared hook implementations."""

from pathlib import Path
import sys

SCRIPT = Path(__file__).resolve()
# Deployed adapters live in ~/.<provider>/hooks beside ~/.claude/hooks; the source tree keeps agents/hooks.
COMMON = SCRIPT.parents[2] / (".claude/hooks" if SCRIPT.parent.parent.name.startswith(".") else "hooks")
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(COMMON / "lib"))

import provider_adapter

ADAPTER = provider_adapter.Adapter(
    provider_adapter.Profile(
        name="codex",
        content_modes=("prompt", "apply-patch"),
        cwd_fallback=provider_adapter.no_cwd,
    )
)


if __name__ == "__main__":
    sys.exit(ADAPTER.main(sys.argv[1:]))
